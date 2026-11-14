"""Compact *technical* creative-body tool contracts, queried per capability.

No prose handbook or visual/genre/shot templates. These are installed tool
argument types; the creative model authors all visual positions, artwork,
sound, timing and editorial structures in its own project.
"""
from __future__ import annotations

_ARG_TYPES={
    "source":"string","source_svg":"string","source_film":"string",
    "asset_id":"string","attestation_id":"string",
    "scene_json":"string","original_film_ir":"string","voice_assets":"string",
    "assets_root":"string","edit":"string","plan":"string","operation":"string","video_job":"string","out":"string",
    "document":"object","base":"string","expected_sha256":"string",
    "width":"integer","height":"integer","fps":"integer",
    "bundle":"string","bundle_sha256":"string","frame_index":"integer",
    "before_bundle":"string","before_sha256":"string",
    "after_bundle":"string","after_sha256":"string",
    "time_seconds":"number","expected":"object","source_witness":"object",
    "gap_color":"string","before_edit":"string","after_edit":"string","focus":"string",
    "numerator":"integer","denominator":"integer","drop_frame":"boolean",
    "timecode":"string",
    "old_workspace":"string",
}
_EXAMPLES_DISALLOWED=True


def real_operation_schema(tool_id,required):
    """Expose one machine-readable ABI instead of a giant markdown manual."""
    if not isinstance(required,(tuple,list)) or any(
            not isinstance(p,str) or p not in _ARG_TYPES for p in required):
        raise ValueError("Backend advertised unknown physical tool arguments")
    props={}
    for name in required:
        kind=_ARG_TYPES[name]
        meta={"type":kind}
        if kind=="integer":
            meta["minimum"]=0 if name=="frame_index" else 1
        if kind=="number":
            meta["minimum"]=0
        props[name]=meta
    optional={
        "body.motion2d":("voice_assets",),
        "body.visual_author":("base","expected_sha256"),
        "body.blender3d":("assets_root",),
        "body.exr_passes":("assets_root",),
        "body.full_decode":("expected",),
        "body.mlt_owned_render":("gap_color",),
        "body.mlt_owned_compare":("focus",),
    }.get(tool_id,())
    for name in optional:
        props[name]=({"type":"string","pattern":"^[a-f0-9]{64}$"}
                     if name=="expected_sha256" else
                     {"type":"string","pattern":"^#[0-9a-fA-F]{6}$"}
                     if name=="gap_color" else
                     {"type":"string","pattern":"^(?:summary|all|picture:[0-7]|sound:[0-3])$"}
                     if name=="focus" else {"type":_ARG_TYPES[name]})
    return {"type":"object",
            "additionalProperties":False,
            "required":list(required),
            "properties":props,
            "provenance":"installed verified executable, not fictional model capability"}
