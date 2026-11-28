"""Physically transform every owned Blender float32 frame via pinned OCIO ACES2.

An independently decoded source-owned EXR bundle is converted from explicitly
declared associated scene-linear CG Rec.709 to a real 16-bit RGB per-frame
display raster, then to fully decoded 10-bit ProRes YUV422. An explicit Rec.2100 PQ
ACES2 view also supports a 1000-nit-target Rec.2020 HDR picture master.
An artist separately supplies sound. No calibrated-monitor, HDR10 static
metadata, universal camera transform or independent artistic certification.
"""
from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from .body_aces2_preview import (
    _physical_config,_float_channels,SOURCE_COLOR,DISPLAY,VIEW,HDR_DISPLAY,HDR_VIEW,
    _MAX_EXR_FRAME_BYTES)
from .body_exr_passes import verify_exr_bundle
from .media_vault import MediaVault,sha256_file,canonical_source_attestations
from .production_qc import full_decode_inspection

_MAX_TOTAL_PIXELS=2000000


def _encode_display_movie(rgb_path,movie,width,height,count,fps,*,display,view):
    """Encode an already display-transformed RGB48 sequence without relighting it."""
    if (display,view)==(DISPLAY,VIEW):
        matrix,primaries,transfer="bt709","bt709","iec61966-2-1"
    elif (display,view)==(HDR_DISPLAY,HDR_VIEW):
        matrix,primaries,transfer="bt2020nc","bt2020","smpte2084"
    else:
        raise ValueError("Unsupported pinned ACES2 display/view pair")
    scale_matrix="bt2020" if matrix=="bt2020nc" else matrix
    filters=f"scale=in_range=full:out_range=limited:out_color_matrix={scale_matrix},format=yuv422p10le"
    filters+=f",setparams=range=limited:color_primaries={primaries}:color_trc={transfer}:colorspace={matrix}"
    cmd=["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-n",
         "-f","rawvideo","-pixel_format","rgb48le",
         "-video_size",f"{width}x{height}","-framerate",str(fps),
         "-i",str(rgb_path),"-an",
         "-vf",filters,
         "-c:v","prores_ks","-profile:v","3",
         "-pix_fmt","yuv422p10le","-color_range","tv",
         "-color_primaries",primaries,"-color_trc",transfer,
         "-colorspace",matrix,"-movflags","+write_colr"]
    if (display,view)==(HDR_DISPLAY,HDR_VIEW):
        # ProRes encoders may omit these frame-header fields even when MOV
        # colr is requested. Both actual coded frames and container must agree.
        cmd.extend(["-bsf:v","prores_metadata=color_primaries=bt2020:color_trc=smpte2084:colorspace=bt2020nc"])
    cmd.append(str(movie))
    proc=subprocess.run(cmd,capture_output=True,text=True,timeout=1200)
    if proc.returncode!=0:
        raise RuntimeError("Real native ACES2 ProRes encode failed: "+proc.stderr[-1200:])
    probe=subprocess.run(["ffprobe","-v","error","-count_frames",
          "-select_streams","v:0","-show_entries",
          "stream=codec_name,pix_fmt,nb_read_frames,r_frame_rate,color_space,color_primaries,color_transfer,color_range",
          "-of","json",str(movie)],capture_output=True,text=True,timeout=60,check=True)
    coded=json.loads(probe.stdout)["streams"][0]
    if (coded.get("codec_name")!="prores" or coded.get("pix_fmt")!="yuv422p10le" or
            coded.get("nb_read_frames")!=str(count) or
            coded.get("r_frame_rate") not in (str(fps),str(fps)+"/1")):
        raise ValueError("A real source frame or 10bit ProRes color stage was lost")
    if (display,view)==(HDR_DISPLAY,HDR_VIEW):
        expected={"color_space":matrix,"color_primaries":primaries,"color_transfer":transfer}
        if any(coded.get(key)!=value for key,value in expected.items()):
            raise ValueError("Encoded HDR picture lost actual Rec.2100 PQ color signaling")
        frames=json.loads(subprocess.check_output(["ffprobe","-v","error","-select_streams","v:0",
            "-show_frames","-show_entries","frame=color_range,color_space,color_primaries,color_transfer",
            "-of","json",str(movie)],timeout=1200))["frames"]
        # MOV stream-level range is not always emitted for ProRes. Verify the
        # decoded frames instead of inferring limited range from a missing tag.
        if len(frames)!=count or any(any(frame.get(k)!=v for k,v in
                {**expected,"color_range":"tv"}.items()) for frame in frames):
            raise ValueError("A decoded HDR frame lost PQ, Rec.2020 or limited-range signaling")
        coded["color_range"]="tv"
    return coded


def render_aces2_scene_movie(plan_file,workspace,vault_root,output):
    import numpy as np

    root=Path(workspace).resolve()
    document=Path(plan_file).resolve()
    dest=Path(output).resolve()
    if (not document.is_relative_to(root) or not document.is_file()
            or document.is_symlink() or not dest.is_relative_to(root)
            or dest.suffix.lower()!=".mov" or dest.exists() or dest.is_symlink()
            or document==dest):
        raise ValueError("Native scene movie requires owned plan and unused MOV")
    plan_sha=sha256_file(document)
    job=json.loads(document.read_text(encoding="utf-8"))
    if (not isinstance(job,dict) or set(job)!={
            "source","source_color_space","alpha_association",
            "scene_linear_background_rgb","display","view"}):
        raise ValueError("Missing exact native source and display transform")
    source=job["source"]
    if (not isinstance(source,dict) or set(source)!={
            "source","asset_id","attestation_id"}
            or not isinstance(source["asset_id"],str)
            or source["source"]!="zx7:sha256:"+source["asset_id"]
            or not isinstance(source["attestation_id"],str)):
        raise ValueError("Missing trusted original VFX source identity")
    if (job["source_color_space"]!=SOURCE_COLOR or
            job["alpha_association"]!="associated_scene_linear" or
            (job["display"],job["view"]) not in ((DISPLAY,VIEW),(HDR_DISPLAY,HDR_VIEW))):
        raise ValueError("Only pinned ACES2 SDR or Rec.2100 PQ original CG display transform accepted")
    hdr=(job["display"],job["view"])==(HDR_DISPLAY,HDR_VIEW)
    backdrop=job["scene_linear_background_rgb"]
    if (not isinstance(backdrop,list) or len(backdrop)!=3 or
            any(type(v) not in (int,float) or not math.isfinite(v)
                or not 0<=v<=1 for v in backdrop)):
        raise ValueError("Original scene background must be finite linear RGB")
    vault=MediaVault(vault_root)
    observed=vault.inspect(source["asset_id"],
                           attestation_id=source["attestation_id"])
    if observed["mime"]!="application/x-zx7-exr-bundle":
        raise ValueError("Only real graph-licensed 32f original EXR frames may be graded")
    processor,ocio_version,ocio_config_hash=_physical_config(job["display"],job["view"])
    dest.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".zx7-aces2-movie-",dir=root) as temp:
        private=Path(temp)
        pinned=private/"source-original.zip"
        with Path(observed["path"]).open("rb") as inp,pinned.open("xb") as out:
            shutil.copyfileobj(inp,out,1024*1024)
            out.flush()
            os.fsync(out.fileno())
        if sha256_file(pinned)!=source["asset_id"]:
            raise ValueError("Licensed scene source changed during codec seal")
        os.chmod(pinned,0o400)
        source_evidence=verify_exr_bundle(pinned)
        with zipfile.ZipFile(pinned) as archive:
            manifest=json.loads(archive.read("manifest.json"))
            frames=manifest["frames"]
            count=source_evidence["original_frame_count"]
            width,height=manifest["width"],manifest["height"]
            fps=manifest["frames_per_second"]
            if (type(width) is not int or type(height) is not int or
                    type(fps) is not int or not 1<=fps<=120 or
                    width<8 or height<8 or count<1 or
                    width*height*count>_MAX_TOTAL_PIXELS):
                raise ValueError("Original frame sequence exceeds bounded live OCIO processor")
            frame_path=private/"working-float32-frame.exr"
            rgb_path=private/"scene-display-rgb48le.raw"
            with rgb_path.open("xb") as raw:
                for index,item in enumerate(frames,1):
                    name=f"frames/frame_{index:04d}.exr"
                    if item["file"]!=name:
                        raise ValueError("Original source has a skipped/reordered frame")
                    entry=archive.getinfo(name)
                    if entry.file_size>_MAX_EXR_FRAME_BYTES:
                        raise ValueError("Native picture frame exceeds OCIO safe memory budget")
                    with archive.open(name) as inp,frame_path.open("wb") as current:
                        shutil.copyfileobj(inp,current,1024*1024)
                    rgba=_float_channels(frame_path)
                    if rgba.shape!=(height,width,4):
                        raise ValueError("Original scene image dimensions changed")
                    coverage=np.clip(rgba[:,:,3:4],0,1)
                    linear=rgba[:,:,:3]+(1-coverage)*np.asarray(
                        backdrop,dtype=np.float32)
                    if not np.isfinite(linear).all():
                        raise ValueError("Nonfinite physical scene-linear color")
                    mapped=np.empty((height*width,3),dtype=np.float64)
                    for pixel,vector in enumerate(linear.reshape(-1,3)):
                        rgb=[float(v) for v in vector]
                        produced=processor.applyRGB(rgb)
                        result=rgb if produced is None else produced
                        if len(result)!=3 or any(not math.isfinite(float(x))
                                                 for x in result):
                            raise ValueError("Real ACES2 created invalid display RGB")
                        mapped[pixel]=result
                    # From actual OCIO float pixels, preserve more than eight
                    # bits before FFmpeg's 10-bit ProRes 422 quantization.
                    raw.write(np.rint(np.clip(mapped,0,1)*65535).
                              astype("<u2").tobytes())
                raw.flush()
                os.fsync(raw.fileno())
            expected_raw=width*height*count*6
            if rgb_path.stat().st_size!=expected_raw:
                raise ValueError("Scene RGB48 raster lost real pixel data")
        movie=private/"verified-aces2-display-scene.mov"
        coded=_encode_display_movie(rgb_path,movie,width,height,count,fps,
                                    display=job["display"],view=job["view"])
        qa=full_decode_inspection(movie,expected={
            "width":width,"height":height,
            "duration_seconds":count/fps,"require_audio":False})
        if (not qa["technical_delivery_verified"] or
                not qa["full_picture_and_sound_decoder_completed"] or
                qa["audio_present"]):
            raise ValueError("Actual full original ACES2 picture failed decoder proof")
        if (sha256_file(pinned)!=source["asset_id"] or
                sha256_file(document)!=plan_sha or
                vault.inspect(source["asset_id"],
                    attestation_id=source["attestation_id"])["mime"]!=
                        "application/x-zx7-exr-bundle"):
            raise ValueError("Original scene, license or director ACES2 intent mutated")
        with movie.open("rb") as encoded:
            os.fsync(encoded.fileno())
        os.link(movie,dest)
    return {"path":str(dest),"sha256":sha256_file(dest),
            "bytes":dest.stat().st_size,"source_exr_sha256":source["asset_id"],
            "source_attestations":canonical_source_attestations([
                {key:source[key] for key in ("asset_id","attestation_id")}]),
            "original_frames":count,"fps":fps,
            "real_ocio_config_sha256":ocio_config_hash,
            "actual_10bit_prores_sdr_scene":not hdr,
            "actual_10bit_prores_rec2100_pq_scene":hdr,
            "actual_display":job["display"],"actual_view":job["view"],
            "decoded_color_signaling":{key:coded.get(key) for key in
                ("color_space","color_primaries","color_transfer","color_range","pix_fmt")},
            "source_soundtrack_intentionally_absent":True,
            "real_original_aces2_frame_transform":True,
            "hdr_master_or_full_professional_grade_certified":False,
            "independent_creative_quality_certified":False}
