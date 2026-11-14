"""Hash ACTUAL media dependencies before each editor/render tool is reused.

A model's filename alone is not provenance. Original clip bytes, sound, font
and project JSON change the execution cache key. This evaluator is body-native
and separate from the creative brain; it cannot choose composition/style.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .media_vault import sha256_file,MediaVault
from .font_registry import resolve_artist_font

_SOURCE_FIELDS={
    "body.inspect":("source",),
    # Pure SMPTE source-frame addresses have no physical file input; the
    # verified rational clock and address fields remain in the trusted DAG
    # input fingerprint. Empty tuple is a real registered adapter, not an
    # imagined media-attestation claim.
    "body.timecode_format":(),
    "body.timecode_parse":(),
    "body.mlt_owned_timecode_format":("edit",),
    "body.mlt_owned_timecode_parse":("edit",),
    "body.resolve_asset":(),
    "body.voice_inventory":("voice_assets",),
    "body.render_edit":("edit",),
    "body.render_edit_owned":("edit",),
    "body.retime":("plan",),
    "body.sequence_cuts":("plan",),
    "body.mlt_owned_export":("plan",),
    "body.mlt_owned_render":("edit",),
    "body.mlt_owned_import":("edit",),
    "body.mlt_owned_relink":("edit",),
    "body.mlt_owned_revision":("edit","operation"),
    "body.mlt_owned_compare":("before_edit","after_edit"),
    "body.timeline_revision":("plan","operation"),
    "body.otio":("edit",),
    "body.otio_owned_export":("plan",),
    "body.otio_owned_import":("edit",),
    "body.vector_png":("source_svg",),
    "body.film_thumbnail":("source_film",),
    "body.asset_vault":("source",),
    "body.composite_mix":("plan",),
    "body.visual_graph":("plan",),
    "body.visual_author":("base",),
    "body.visual_document":("plan",),
    "body.motion_project":("plan",),
    "body.motion_export":("bundle",),
    "body.film_finish":("plan",),
    "body.color_lut":("plan",),
    "body.full_decode":("source",),
    "body.loudness":("plan",),
    "body.review":("plan",),
    "body.temporal_evidence":("plan",),
    "body.review_data":("bundle",),
    "body.review_frame":("bundle",),
    "body.review_compare":("before_bundle","after_bundle"),
    "body.generate_video":("video_job",),
    "body.blender3d":("scene_json","assets_root"),
    "body.cgi_shot":("plan",),
    "body.planar_insert":("plan",),
    "body.exr_passes":("scene_json","assets_root"),
    "body.aces2_preview":("plan",),
    "body.aces2_movie":("plan",),
    "body.exr_checkpoint":("scene_json",),
    "body.motion2d":("original_film_ir","voice_assets"),
}
_NESTED_SOURCE_KEYS=frozenset(("source","path","project","image_path","texture_path",
                               "model_path","audio_path","video_path"))
_PRODUCTION_SUFFIXES=frozenset((
    ".mp4",".webm",".mov",".mkv",".png",".jpg",".jpeg",".svg",
    ".wav",".flac",".mp3",".json",".blend",".glb",".gltf",
    ".otf",".ttf",".exr",".tiff",".webp",".zxmotion"))


def _file(root,relative):
    if not isinstance(relative,str) or not relative or Path(relative).is_absolute():
        raise ValueError("Trusted creative material must use relative workspace paths")
    raw=Path(relative)
    if ".." in raw.parts:
        raise ValueError("Model source cannot escape creative workspace")
    target=(root/raw).resolve()
    if not target.is_relative_to(root) or not target.exists():
        raise ValueError("Missing actual source material: "+relative)
    return target


def _nested_sources(value,root,found):
    if isinstance(value,dict):
        for key,datum in value.items():
            if key=="source" and isinstance(datum,str) and datum.startswith("zx7:sha256:"):
                digest=datum[len("zx7:sha256:"):]
                if value.get("asset_id")!=digest or not isinstance(value.get("attestation_id"),str):
                    raise ValueError("Machine-neutral media reference lacks matching custody identity")
                observed=MediaVault(root/"vault").inspect(digest,
                    attestation_id=value["attestation_id"])
                physical=Path(observed["path"]).resolve()
                if not physical.is_relative_to(root):
                    raise ValueError("Verified source escaped original production workspace")
                found.add(physical)
            elif (key in _NESTED_SOURCE_KEYS and isinstance(datum,str)
                    and Path(datum).suffix.lower() in _PRODUCTION_SUFFIXES):
                path=_file(root,datum)
                if path.is_file():
                    found.add(path)
            elif isinstance(datum,(dict,list)):
                _nested_sources(datum,root,found)
    elif isinstance(value,list):
        for item in value:
            _nested_sources(item,root,found)


def _authored_typefaces(value,selected):
    if isinstance(value,dict):
        if value.get("type")=="text":
            selected.add(value.get("font","sans"))
        for child in value.values():
            if isinstance(child,(dict,list)):_authored_typefaces(child,selected)
    elif isinstance(value,list):
        for child in value:_authored_typefaces(child,selected)


def fingerprint_physical_inputs(tool_id,inputs,workspace):
    """Only original source inputs are inspected, not the output path."""
    if not isinstance(inputs,dict):
        raise ValueError("Executable studio inputs must be an object")
    root=Path(workspace).resolve()
    keys=_SOURCE_FIELDS.get(tool_id)
    if keys is None:
        # An administrator-added provider must supply its own material digest,
        # not receive a claim of comprehensive physical verification.
        raise ValueError("Unregistered tool needs trusted source-fingerprint adapter")
    found=set()
    selected_fonts=set()
    if tool_id=="body.resolve_asset":
        # Resolve by actual immutable CAS bytes and exact owner attestation.
        # An argument pair alone is NEVER enough to advertise a usable source.
        receipt=MediaVault(root/"vault").inspect(
            inputs.get("asset_id"),attestation_id=inputs.get("attestation_id"))
        original=Path(receipt["path"]).resolve()
        if not original.is_relative_to(root):
            raise ValueError("Source custody escaped the original owner workspace")
        found.add(original)
    for key in keys:
        source=inputs.get(key)
        if source is None:
            continue
        p=_file(root,source)
        if p.is_file():
            found.add(p)
            if p.suffix.lower()==".mlt" and tool_id=="body.mlt_owned_relink":
                from .body_mlt_relink import inspect_relocated_mlt
                inspected=inspect_relocated_mlt(p,root,inputs.get("old_workspace"))
                found.add(inspected["report_path"])
                for reference in inspected["references"]:
                    found.add(reference["path"])
            if p.suffix.lower()==".mlt" and tool_id in ("body.mlt_owned_render","body.mlt_owned_import","body.mlt_owned_revision","body.mlt_owned_compare","body.mlt_owned_timecode_format","body.mlt_owned_timecode_parse"):
                from .body_mlt_editor import verify_owned_mlt_project
                import xml.etree.ElementTree as ET
                verify_owned_mlt_project(p)
                doc=ET.fromstring(p.read_bytes())
                for node in doc.findall("producer"):
                    props={c.get("name"):c.text for c in node.findall("property")}
                    file=Path(props["resource"]).resolve()
                    if not file.is_relative_to(root):
                        raise ValueError("MLT original asset escaped owner workspace")
                    found.add(file)
            if p.suffix.lower()==".otio" and tool_id=="body.otio_owned_import":
                from .body_sequence_otio import import_verified_sequence_otio
                imported=import_verified_sequence_otio(p,root,root/"vault")
                for shot in imported["plan"]["clips"]:
                    receipt=MediaVault(root/"vault").inspect(
                        shot["asset_id"],attestation_id=shot["attestation_id"])
                    original=Path(receipt["path"]).resolve()
                    if not original.is_relative_to(root):
                        raise ValueError("Editable source escaped the owner workspace")
                    found.add(original)
            if p.suffix.lower()==".json":
                document=json.loads(p.read_text(encoding="utf-8"))
                _nested_sources(document,root,found)
                if tool_id=="body.render_edit_owned":
                    from .body_owned_edit import validate_owned_edit
                    validate_owned_edit(document,root,root/"vault")
                if tool_id=="body.otio_owned_export":
                    from .body_sequence_cuts import plan_verified_sequence
                    plan_verified_sequence(document,root,root/"vault")
                if tool_id=="body.motion2d":
                    _authored_typefaces(document,selected_fonts)
        elif p.is_dir():
            for child in p.rglob("*"):
                if child.is_symlink():
                    raise ValueError("Untrusted linked media in creative asset folder")
                if child.is_file():
                    resolved=child.resolve()
                    if not resolved.is_relative_to(root):
                        raise ValueError("Asset path escaped the original production")
                    found.add(resolved)
    physical=[{"relative":str(path.relative_to(root)),
             "bytes":path.stat().st_size,"sha256":sha256_file(path)}
            for path in sorted(found)]
    if tool_id=='body.generate_video':
        from .generative_video_providers import generator_material_identity
        job=json.loads(_file(root,inputs['video_job']).read_text())
        physical.append({'trusted_generator_deployment':generator_material_identity(
            os.getenv('ZX7_VIDEO_DEPLOYMENTS','models/creative-video'),job['model_id']),
            'operator_local_endpoint':os.getenv('ZX7_COMFY_API')})
    for name in sorted(selected_fonts):
        font=Path(resolve_artist_font(name))
        physical.append({"installed_typeface":name,"resolved_font":str(font.resolve()),
                         "bytes":font.stat().st_size,"sha256":sha256_file(font)})
    return physical
