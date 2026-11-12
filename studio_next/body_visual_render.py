"""Sealed media I/O for native editable visual graphs.

Pixel math is BODY code. Deliveries are sRGB PNG, lossless RGBA PNG-in-MOV,
and lossless float32 EXR stills. Audio stays on separate editable tracks.
"""
from __future__ import annotations
import hashlib
import io
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import time
from .body_animation import curve_value
from .body_visual_graph import VisualGraph,associate,to_linear,rgba8
from .composite_mix import _exact_media,sealed_attested_original
from .media_vault import MediaVault,sha256_file
from .production_qc import full_decode_inspection


def _probe(path):
    result=subprocess.run(["ffprobe","-v","error","-select_streams","v:0","-show_streams","-of","json",str(path)],
        check=True,capture_output=True,text=True,timeout=60)
    streams=json.loads(result.stdout)["streams"]
    if len(streams)!=1:raise ValueError("Source needs a physically decodable video stream")
    return streams[0]


class SealedGraphSources:
    def __init__(self,graph,root,vault,private):
        self.graph,self.root,self.vault,self.private=graph,root,vault,private
        self.originals,self.snapshots,self.sources,self.frames={},{},{},{}
        self.last=None;budget=graph.budget;total_bytes=0
        for name in graph.order:
            node=graph.nodes[name]
            if node["op"]!="source":continue
            p=node["params"];media=p["media"]
            original=_exact_media(media,vault,root,need="visual source")
            record=vault.inspect(media["asset_id"],attestation_id=media["attestation_id"])
            allowed={"image":{"image/png","image/jpeg","image/x-exr"},"video":{"video/mp4","video/quicktime","video/webm"}}
            if record["mime"] not in allowed[p["kind"]]:raise ValueError("Graph source kind differs from attested media")
            self.originals[str(original)]=media["asset_id"]
            frozen=sealed_attested_original(vault,media["asset_id"],media["attestation_id"],private,self.snapshots)
            self.sources[name]=(frozen,media,p["color_space"])
            if p["kind"]=="image":
                if record["mime"]=="image/x-exr":
                    if p["color_space"]!="linear_srgb":raise ValueError("EXR input must declare linear_srgb and alpha association")
                else:
                    if p["color_space"]!="srgb":raise ValueError("Raster source requires sRGB or embedded ICC conversion")
                    self._check_image(frozen)
                self.frames[name]={0:frozen};continue
            meta=_probe(frozen);w,h=meta["width"],meta["height"]
            if w*h>budget.max_pixels:raise ValueError("Source video exceeds host pixel budget")
            pixel_format=meta.get("pix_fmt","")
            if int(meta.get("bits_per_raw_sample","0") or 0)>8 or any(x in pixel_format for x in ("10","12","14","16","f32")):
                raise ValueError("Graph video decoder currently requires 8-bit source; high-depth conversion must be explicit")
            expected={"srgb":"iec61966-2-1","bt709":"bt709"}[p["color_space"]]
            if meta.get("color_transfer","unknown") not in ("unknown","unspecified",expected):
                raise ValueError("Declared source transfer conflicts with native media tags")
            if meta.get("color_primaries","unknown") not in ("unknown","unspecified","bt709"):
                raise ValueError("Source primaries need an explicit supported conversion")
            requested=set();selection=graph.plan["render"]
            for frame in range(selection["first_frame"],selection["first_frame"]+selection["frame_count"]):
                index=curve_value(p["frame"],frame)
                if not math.isfinite(index) or index<0 or abs(index-round(index))>1e-6:
                    raise ValueError("Sampling must select exact original source frame indices")
                requested.add(round(index))
            if max(requested)>=budget.max_source_frames:raise ValueError("Source decode extent exceeds host frame budget")
            total_bytes+=len(requested)*w*h*4
            if total_bytes>budget.max_decode_bytes:raise ValueError("Source frames exceed host decode storage budget")
            folder=private/("decoded-"+name);folder.mkdir();selected=sorted(requested)
            script=folder/"select.ffilter"
            script.write_text("select='"+"+".join("eq(n,"+str(i)+")" for i in selected)+"'")
            # One decode per source for original-clock reverse/hold/reorder.
            # Integer-only filter is trusted host syntax, never model FFmpeg code.
            subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-xerror","-nostdin","-threads","1",
                "-i",str(frozen),"-map","0:v:0","-filter_script:v",str(script),"-vsync","0",
                "-frames:v",str(len(selected)),"-pix_fmt","rgba","-threads","1",str(folder/"frame-%08d.png")],
                check=True,capture_output=True,timeout=600)
            files=sorted(folder.glob("frame-*.png"))
            if len(files)!=len(selected):raise ValueError("Requested original video frame does not exist")
            self.frames[name]=dict(zip(selected,files))

    def _check_image(self,path):
        from PIL import Image
        with path.open("rb") as stream:header=stream.read(26)
        if header.startswith(b"\x89PNG\r\n\x1a\n") and header[24] not in (1,2,4,8):
            raise ValueError("Source PNG must have at most 8-bit channels")
        with Image.open(path) as image:
            if image.width*image.height>self.graph.budget.max_pixels:raise ValueError("Source image exceeds host pixel budget")
            if getattr(image,"n_frames",1)!=1:raise ValueError("Animated image needs explicit video conversion")

    def __call__(self,name,frame):
        import numpy as np
        from PIL import Image,ImageCms
        key=(name,frame)
        if self.last is not None and self.last[0]==key:return self.last[1]
        if frame not in self.frames[name]:raise ValueError("Source frame is outside the verified render interval")
        path=self.frames[name][frame]
        if self.sources[name][2]=="linear_srgb":
            from .body_visual_exr import read_float_rgba
            p=self.graph.nodes[name]["params"]
            result=read_float_rgba(path,budget=self.graph.budget,alpha_mode=p["alpha_mode"],channels=p.get("channels"))
            self.last=(key,result)
            return result
        self._check_image(path)
        with Image.open(path) as image:
            rgba=image.convert("RGBA");icc=image.info.get("icc_profile")
            if icc:
                if self.sources[name][2]!="srgb":raise ValueError("ICC conflicts with declared video transfer function")
                rgb=ImageCms.profileToProfile(image.convert("RGB"),ImageCms.ImageCmsProfile(io.BytesIO(icc)),
                    ImageCms.createProfile("sRGB"),outputMode="RGB")
                alpha=rgba.getchannel("A");rgba=rgb.convert("RGBA");rgba.putalpha(alpha)
            pixels=np.array(rgba,dtype=np.float32)/255
        pixels[...,:3]=to_linear(pixels[...,:3],self.sources[name][2])
        result=associate(pixels);self.last=(key,result)
        return result

    def verify(self):
        for path,digest in self.originals.items():
            if sha256_file(path)!=digest:raise ValueError("Original source changed during visual rendering")
        for (digest,_),path in self.snapshots.items():
            if sha256_file(path)!=digest:raise ValueError("Sealed source changed during visual rendering")
        for _,media,_ in self.sources.values():self.vault.inspect(media["asset_id"],attestation_id=media["attestation_id"])


def render_visual_graph(plan_file,workspace,vault_root,output,*,
                        budget=None,convolution_backend="numpy"):
    from PIL import Image,PngImagePlugin
    root,plan_file,output=Path(workspace).resolve(),Path(plan_file).resolve(),Path(output).resolve()
    if not plan_file.is_relative_to(root) or not output.is_relative_to(root) or output.exists():
        raise ValueError("Visual graph requires original workspace plan and new output")
    # Bind the receipt to exactly the bytes parsed, rather than hashing and
    # reopening a mutable file. A concurrent source swap must not substitute
    # different creative directions between those two operations.
    with plan_file.open("rb") as stream:raw_plan=stream.read(16777217)
    if len(raw_plan)>16777216:raise ValueError("Visual graph exceeds host input size budget")
    plan_sha=hashlib.sha256(raw_plan).hexdigest()
    graph=VisualGraph(json.loads(raw_plan),budget=budget,
                      convolution_backend=convolution_backend)
    selection=graph.plan["render"];suffix={"png":".png","rgba_mov":".mov","exr32":".exr"}[selection["format"]]
    if output.suffix.lower()!=suffix:raise ValueError("Output suffix differs from authored format")
    if graph.canvas["width"]*graph.canvas["height"]*4*selection["frame_count"]>graph.budget.max_decode_bytes:
        raise ValueError("Output verification exceeds host decode storage budget")
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".zx7-visual-graph-",dir=output.parent) as directory:
        private=Path(directory);sources=SealedGraphSources(graph,root,MediaVault(vault_root),private)
        stage=private/("visual"+suffix);first,count=selection["first_frame"],selection["frame_count"]
        digests=[];clipped=0;encoder=None
        try:
            with (private/"encoder.log").open("wb") as log:
                if selection["format"]=="rgba_mov":
                    w,h=graph.canvas["width"],graph.canvas["height"];rate=graph.fps
                    encoder=subprocess.Popen(["ffmpeg","-hide_banner","-loglevel","error","-xerror",
                        "-f","rawvideo","-pixel_format","rgba","-video_size",f"{w}x{h}",
                        "-framerate",f"{rate.numerator}/{rate.denominator}","-i","pipe:0","-an","-c:v","png",
                        "-pix_fmt","rgba","-threads","1","-color_primaries","bt709","-color_trc","iec61966-2-1",
                        "-colorspace","rgb","-movflags","+faststart",str(stage)],
                        stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=log)
                started=time.monotonic()
                for frame in range(first,first+count):
                    floating=graph.frame(frame,source_provider=sources)
                    if selection["format"]=="exr32":
                        from .body_visual_exr import write_float_rgba
                        write_float_rgba(stage,floating,plan_sha256=plan_sha,budget=graph.budget)
                        digests.append(hashlib.sha256(floating.tobytes()).hexdigest())
                        continue
                    pixels,outside=rgba8(floating);clipped+=outside
                    data=pixels.tobytes();digests.append(hashlib.sha256(data).hexdigest())
                    if encoder is None:
                        metadata=PngImagePlugin.PngInfo();metadata.add_text("zx7_graph_sha256",plan_sha);metadata.add(b"sRGB",b"\x00")
                        Image.fromarray(pixels).save(stage,pnginfo=metadata)
                    else:encoder.stdin.write(data)
                    if time.monotonic()-started>3600:raise TimeoutError("Visual render exceeded host execution budget")
                if encoder is not None:
                    encoder.stdin.close()
                    if encoder.wait(timeout=max(1,3600-(time.monotonic()-started)))!=0:
                        raise RuntimeError("RGBA encoder failed: "+(private/"encoder.log").read_text()[-2000:])
        finally:
            if encoder is not None and encoder.poll() is None:encoder.kill();encoder.wait(timeout=15)
            if encoder is not None and encoder.stdin and not encoder.stdin.closed:encoder.stdin.close()
        if selection["format"]=="png":
            with Image.open(stage) as image:
                image.load()
                if hashlib.sha256(image.convert("RGBA").tobytes()).hexdigest()!=digests[0]:
                    raise RuntimeError("Exported PNG differs from rendered pixels")
        elif selection["format"]=="rgba_mov":
            check=full_decode_inspection(stage,expected={"width":graph.canvas["width"],"height":graph.canvas["height"],
                "duration_seconds":float(count/graph.fps),"require_audio":False})
            if not check["technical_delivery_verified"] or check["audio_present"]:raise RuntimeError("Visual motion failed full decode")
            raw=private/"decoded.rgba"
            subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-xerror","-nostdin","-i",str(stage),
                "-map","0:v:0","-vsync","0","-f","rawvideo","-pix_fmt","rgba",str(raw)],
                check=True,capture_output=True,timeout=600)
            size=graph.canvas["width"]*graph.canvas["height"]*4
            with raw.open("rb") as stream:
                for digest in digests:
                    if hashlib.sha256(stream.read(size)).hexdigest()!=digest:raise RuntimeError("Decoded motion pixels/alpha differ")
                if stream.read(1):raise RuntimeError("Encoder inserted unrequested frames")
        if sha256_file(plan_file)!=plan_sha:raise ValueError("Visual project changed during rendering")
        sources.verify()
        with stage.open("rb") as stream:os.fsync(stream.fileno())
        os.link(stage,output)
    return {"path":str(output),"sha256":sha256_file(output),"bytes":output.stat().st_size,
        "plan_sha256":plan_sha,"original_first_frame":first,"frames":count,"decoded_rgba_exact":True,
        "rendered_frame_pixel_sha256":digests,"working_precision":"float32_linear_srgb_associated_alpha",
        "delivery_precision":"float32_linear_srgb_associated_rgba" if selection["format"]=="exr32" else "8bit_srgb_straight_rgba",
        "explicitly_clipped_rgb_components":clipped,
        "audio_policy":"separate_editable_tracks","source_assets":len(sources.sources),
        "project_node_fingerprints":graph.node_fingerprints(),
        "convolution_backend":graph.convolution_backend,
        "convolution_backend_runtime_version": (
            __import__("scipy").__version__ if graph.convolution_backend=="scipy"
            else __import__("numpy").__version__),
        "aesthetic_quality_approved":False}
