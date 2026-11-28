"""Exact built-in ASWF OpenColorIO ACES 2.0 SDR *preview* of owned 32f EXR.

The original source is a SHA256+attestation bound, fully decoded Blender EXR
archive; only a verified installed OCIO 2.5 built-in ACES2 config is used.
Source primaries, display and view are an explicit technical contract, not a
creative preset or unverified camera-input transform. This makes a scene-linear
CG-to-display proof, NOT an HDR master or universal OCIO/VFX color pipeline.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

from .body_exr_passes import verify_exr_bundle, inspect_real_exr_frame
from .media_vault import MediaVault, sha256_file

OCIO_BUILTIN="cg-config-v4.0.0_aces-v2.0_ocio-v2.5"
SOURCE_COLOR="Linear Rec.709 (sRGB)"
DISPLAY="sRGB - Display"
VIEW="ACES 2.0 - SDR 100 nits (Rec.709)"
HDR_DISPLAY="Rec.2100-PQ - Display"
HDR_VIEW="ACES 2.0 - HDR 1000 nits (Rec.2020)"
_MAX_EXR_FRAME_BYTES=80*1024*1024


def _physical_config(display=DISPLAY,view=VIEW):
    if (display,view) not in ((DISPLAY,VIEW),(HDR_DISPLAY,HDR_VIEW)):
        raise ValueError("Unsupported pinned ACES2 display/view pair")
    import PyOpenColorIO as OCIO
    version=importlib.metadata.version("opencolorio")
    numbers=version.split(".")
    if (len(numbers)<2 or not all(s.isdigit() for s in numbers[:2])
            or tuple(map(int,numbers[:2]))<(2,5)):
        raise RuntimeError("An actual OCIO 2.5+ processor is required for ACES 2.0")
    config=OCIO.Config.CreateFromBuiltinConfig(OCIO_BUILTIN)
    if config.getColorSpace(SOURCE_COLOR) is None:
        raise RuntimeError("Pinned ACES2 config does not expose original scene Rec.709")
    transform=OCIO.DisplayViewTransform()
    transform.setSrc(SOURCE_COLOR)
    transform.setDisplay(display)
    transform.setView(view)
    processor=config.getProcessor(transform)
    cpu=processor.getDefaultCPUProcessor()
    config_hash=hashlib.sha256(config.serialize().encode("utf-8")).hexdigest()
    return cpu,version,config_hash


def _float_channels(path):
    import numpy as np
    import OpenEXR
    inspected=inspect_real_exr_frame(path)
    with OpenEXR.File(str(path),separate_channels=True) as exr:
        for part in exr.parts:
            channel_map=part.channels
            def find(suffix):
                matches=[v.pixels for k,v in channel_map.items()
                         if k=="Combined."+suffix or
                            k.endswith(".Combined."+suffix)]
                return matches[0] if len(matches)==1 else None
            values=[find(k) for k in "RGBA"]
            if any(value is None for value in values):
                continue
            rgba=np.stack(values,axis=-1).astype(np.float32)
            if rgba.shape!=(inspected["height"],inspected["width"],4):
                raise ValueError("Decoded source scene color channels have unequal geometry")
            if not np.isfinite(rgba).all():
                raise ValueError("Original EXR contains non-finite picture samples")
            if (np.min(rgba[:,:,3])<-.00001 or
                    np.max(rgba[:,:,3])>1.00001):
                raise ValueError("Original scene alpha is outside physical 0..1 coverage")
            return rgba
    raise ValueError("No exact scene-linear Combined RGBA pixels in owned EXR")


def render_aces_2_sdr_preview(plan_file,workspace,vault_root,output):
    import numpy as np
    from PIL import Image,PngImagePlugin
    root=Path(workspace).resolve()
    original=Path(plan_file).resolve()
    dest=Path(output).resolve()
    if (not original.is_file() or not original.is_relative_to(root)
            or original.is_symlink() or not dest.is_relative_to(root)
            or dest.suffix.lower()!=".png" or dest.exists() or dest.is_symlink()):
        raise ValueError("ACES preview requires an original local plan and unused PNG")
    prior=sha256_file(original)
    plan=json.loads(original.read_text(encoding="utf-8"))
    if (not isinstance(plan,dict) or set(plan)!={
                "source","frame_index","source_color_space","alpha_association",
                "scene_linear_background_rgb","display","view"}):
        raise ValueError("ACES preview has incomplete original color pipeline declaration")
    source=plan["source"]
    if (not isinstance(source,dict) or set(source)!={
                "source","asset_id","attestation_id"}
            or not isinstance(source["asset_id"],str)
            or source["source"]!="zx7:sha256:"+source["asset_id"]
            or not isinstance(source["attestation_id"],str)):
        raise ValueError("Owned EXR bundle needs exact source identity and attestation")
    if (plan["source_color_space"]!=SOURCE_COLOR or
            plan["alpha_association"]!="associated_scene_linear" or
            plan["display"]!=DISPLAY or plan["view"]!=VIEW):
        raise ValueError("Unsupported original input primaries, alpha or pinned ACES2 view")
    backdrop=plan["scene_linear_background_rgb"]
    if (not isinstance(backdrop,list) or len(backdrop)!=3 or any(
            type(v) not in (int,float) or not math.isfinite(v) or
            not 0<=v<=1 for v in backdrop)):
        raise ValueError("Explicit 0..1 linear backdrop required for premultiplied EXR")
    idx=plan["frame_index"]
    if type(idx) is not int or not 1<=idx<=9999:
        raise ValueError("Original frame index must be an exact positive integer")
    vault=MediaVault(vault_root)
    item=vault.inspect(source["asset_id"],attestation_id=source["attestation_id"])
    if item["mime"]!="application/x-zx7-exr-bundle":
        raise ValueError("Only a trusted original EXR frame bundle may enter ACES2")
    in_archive=Path(item["path"])
    cpu,ocio_version,ocio_hash=_physical_config()
    dest.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".zx7-aces2-",dir=root) as private_dir:
        private=Path(private_dir)
        frozen=private/"source-original.zip"
        with in_archive.open("rb") as src,frozen.open("xb") as sink:
            shutil.copyfileobj(src,sink,1024*1024)
            sink.flush();os.fsync(sink.fileno())
        if sha256_file(frozen)!=source["asset_id"]:
            raise ValueError("Original scene-linear EXR source changed during sealing")
        os.chmod(frozen,0o400)
        actual=verify_exr_bundle(frozen)
        if idx>actual["original_frame_count"]:
            raise ValueError("Original chosen camera frame is outside decoded EXR pass bundle")
        frame_name=f"frames/frame_{idx:04d}.exr"
        extracted=private/"original-32f.exr"
        with zipfile.ZipFile(frozen) as bundle:
            entry=bundle.getinfo(frame_name)
            if entry.file_size>_MAX_EXR_FRAME_BYTES:
                raise ValueError("Native preview frame exceeds bounded original pixel budget")
            with bundle.open(frame_name) as stream,extracted.open("xb") as out:
                shutil.copyfileobj(stream,out,1024*1024)
        original_exr_sha=sha256_file(extracted)
        rgba=_float_channels(extracted)
        height,width=rgba.shape[:2]
        # Bounded model preview, never reinterpreted as a high-resolution
        # original or final mastering raster.
        stepy=max(1,math.ceil(height/180))
        stepx=max(1,math.ceil(width/320))
        pix=rgba[::stepy,::stepx,:].copy()
        # ACES2 display transform is performed *after* compositing associated
        # linear color against an artist-declared scene-linear background.
        alpha=np.clip(pix[:,:,3:4],0,1)
        linear=pix[:,:,:3]+(1-alpha)*np.asarray(backdrop,dtype=np.float32)
        if not np.isfinite(linear).all():
            raise ValueError("Invalid premultiplied scene-linear combination")
        shown=[]
        for px in linear.reshape(-1,3):
            rgb=[float(x) for x in px]
            processed=cpu.applyRGB(rgb)
            values=rgb if processed is None else processed
            if len(values)!=3 or not all(math.isfinite(float(v)) for v in values):
                raise ValueError("Physical OCIO view created invalid display pixels")
            shown.append([min(255,max(0,int(round(float(v)*255)))) for v in values])
        rendered=np.asarray(shown,dtype=np.uint8).reshape(
            (pix.shape[0],pix.shape[1],3))
        metadata=PngImagePlugin.PngInfo()
        properties={
            "original_archive_sha256":source["asset_id"],
            "original_frame_sha256":original_exr_sha,
            "original_frame_index":str(idx),
            "ocio_library_version":ocio_version,
            "ocio_builtin_config":OCIO_BUILTIN,
            "ocio_builtin_config_sha256":ocio_hash,
            "original_declared_source_space":SOURCE_COLOR,
            "actual_display":DISPLAY,
            "actual_view":VIEW,
            "alpha_semantics":"associated_linear_composited_before_display",
            "color_output_kind":"8-bit display-referred review; not HDR delivery",
        }
        for k,v in properties.items():
            metadata.add_text("zx7_"+k,str(v))
        staged=private/"verified-aces2-preview.png"
        Image.fromarray(rendered,"RGB").save(staged,pnginfo=metadata)
        with Image.open(staged) as checked:
            checked.load()
            if (checked.format!="PNG" or checked.mode!="RGB" or
                    checked.size!=(rendered.shape[1],rendered.shape[0]) or
                    checked.info["zx7_ocio_builtin_config_sha256"]!=ocio_hash):
                raise ValueError("Native ACES2 image did not survive independent PNG decoding")
        if (sha256_file(frozen)!=source["asset_id"] or
                sha256_file(original)!=prior or
                vault.inspect(source["asset_id"],attestation_id=source["attestation_id"])["mime"]!="application/x-zx7-exr-bundle"):
            raise ValueError("Original owned frame or director color intent changed during preview")
        os.link(staged,dest)
    return {"path":str(dest),"sha256":sha256_file(dest),
            "bytes":dest.stat().st_size,
            "source_archive_sha256":source["asset_id"],
            "actual_Ocio_ACES2_SDR_view_applied":True,
            "scene_linear_to_HDR_mastering_certified":False,
            "human_creative_quality_certified":False}
