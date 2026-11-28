"""Discover real locally installed creative applications for ONE artistic brain.

Capabilities are tools, not independent decision-making agents or visual
templates. Declaring a tool available does NOT imply the Studio already has
a validated rendering adapter, a GPU, model weights, media rights or premium
results. New locally installed tools can be discovered by updating the data
catalog, without rewriting the Director or applying a predefined art style.

Never accept model-originated shell commands or executable paths.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path


# Non-artistic software probes only. Art direction, styles, genres, composition
# and choice of tools are entirely up to the film mind.
FOSS_TOOL_CANDIDATES = (
    {"id":"blender","executables":["blender"],"craft":["full 3D","animation","VFX","compositing","3D typography"],"license":"GPL", "adapter":"blender3d"},
    {"id":"ffmpeg","executables":["ffmpeg","ffprobe"],"craft":["nonlinear clip finishing","color and audio filters","video encoding","audio mixing","media inspection"],"license":"GPL/LGPL depends on build","adapter":"edit_timeline"},
    {"id":"inkscape","executables":["inkscape"],"craft":["original vector design","typography","logos","posters","thumbnails","SVG"],"license":"GPL","adapter":None},
    {"id":"gimp","executables":["gimp"],"craft":["raster design","retouching","posters","thumbnail imaging","photo compositing"],"license":"GPL","adapter":None},
    {"id":"krita","executables":["krita"],"craft":["digital painting","concept art","illustration","frame animation"],"license":"GPL","adapter":None},
    {"id":"kdenlive","executables":["kdenlive"],"craft":["editorial timeline","keyframed video effects","video editing"],"license":"GPL","adapter":None},
    {"id":"mlt","executables":["melt"],"craft":["headless nonlinear video compositions","transitions","filters","multitrack editing"],"license":"GPL/LGPL depends on build","adapter":None},
    {"id":"gstreamer-ges","executables":["ges-launch-1.0"],"craft":["interactive layered editing timeline","proxy preview","GStreamer editing-service effects"],"license":"LGPL; dependent plugins separately checked","adapter":None},
    {"id":"opencolorio-cli","executables":["ocioconvert"],"craft":["ACES/OpenColorIO scene-referred transform","color-space conversion"],"license":"BSD-3-Clause; config/asset licenses separately checked","adapter":None},
    {"id":"openimageio-cli","executables":["oiiotool"],"craft":["multi-channel image pipelines","EXR processing","HDR compositing intermediates"],"license":"BSD-3-Clause; dependent formats/plugins separately checked","adapter":None},
    {"id":"openusd-cli","executables":["usdcat"],"craft":["composed USD asset inspection","3D scene graph interchange","non-destructive scene layering"],"license":"Apache-2.0; dependent asset licenses separately checked","adapter":None},
    {"id":"natron","executables":["NatronRenderer"],"craft":["node VFX","keying","tracking","compositing"],"license":"GPL","adapter":None},
    {"id":"opentoonz","executables":["OpenToonz"],"craft":["drawn 2D frame animation","traditional character animation"],"license":"BSD style","adapter":None},
    {"id":"godot","executables":["godot","godot4"],"craft":["real-time 2D/3D animated scenes","interactive previews"],"license":"MIT","adapter":None},
    {"id":"sox","executables":["sox"],"craft":["audio effects","sound cleanup","audio mixing"],"license":"GPL/LGPL dependencies","adapter":None},
    {"id":"audacity","executables":["audacity"],"craft":["waveform audio editing","dialogue repair"],"license":"GPL","adapter":None},
)


APPLICATION_OPERATIONS = {
    "blender": ("body.blender3d", "body.exr_passes"),
    "ffmpeg": ("body.composite_mix", "body.sequence_cuts", "body.film_finish", "body.subtitle_delivery"),
    "inkscape": ("body.vector_png",),
    "mlt": ("body.mlt_owned_export", "body.mlt_owned_import", "body.mlt_owned_render"),
}


def probe_creative_tools(*, finder=None, specs=FOSS_TOOL_CANDIDATES,
                         installed_operation_ids=frozenset()):
    """Binary presence checked on THIS machine, not an imagined cloud install."""
    finder=finder or shutil.which
    found=[]
    known=set()
    for spec in specs:
        name=spec["id"]
        if name in known or not isinstance(name,str):
            raise ValueError("Duplicate or invalid tool catalog entry")
        known.add(name)
        names=spec["executables"]
        if not isinstance(names,list) or not names:
            raise ValueError("Missing application executable candidates")
        options=[(p,finder(p)) for p in names]
        chosen=next(((n,path) for n,path in options if path),None)
        found.append({
            "tool_id":name,
            "installed_on_current_machine":bool(chosen),
            "resolved_executable":chosen[1] if chosen else None,
            "creative_capabilities":list(spec["craft"]),
            "license_family":spec["license"],
            "registered_execution_adapter":next(iter(
                APPLICATION_OPERATIONS.get(name, ())),None),
            "executable_body_operations":[op for op in APPLICATION_OPERATIONS.get(name,())
                                          if op in installed_operation_ids],
            "can_render_in_zx7_now":bool(chosen and any(
                op in installed_operation_ids for op in APPLICATION_OPERATIONS.get(name,()))),
            "requires_authorized_assets_and_production_validation":True,
            "can_make_arbitrary_cinematic_output":False,
        })
    return found


def creative_tool_inventory(*, finder=None, installed_operation_ids=None):
    # The true local production capacities are dynamically probed. Uninstalled
    # software is shown as candidate tools, not marketed as working.
    if installed_operation_ids is None:
        # Tests that substitute only binary lookup do not establish executable
        # adapters. Normal discovery uses the same authority as LiveBodySignal.
        installed_operation_ids=frozenset()
        if finder is None:
            from .body_integration import body_catalog
            with tempfile.TemporaryDirectory(prefix="zx7-tool-probe-") as root:
                installed_operation_ids=body_catalog(root).executable_ids(
                    allowed_access={"read","write"})
    candidates=probe_creative_tools(finder=finder,
        installed_operation_ids=installed_operation_ids)
    return {
        "actual_installed_tools":[x for x in candidates if x["installed_on_current_machine"]],
        "not_installed_tools":[x for x in candidates if not x["installed_on_current_machine"]],
        "disclosure":"Tool installation does not mean artistic competence or a wired working render adapter",
        "policy":"Never generate a fabricated substitute just because an artistic tool is absent",
        "creative_scope_not_restricted_to_catalog":True,
        "art_and_tool_choice_owned_by_single_model":True,
    }


def write_inventory(path,*,finder=None):
    document=creative_tool_inventory(finder=finder)
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(document,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return document


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    found=write_inventory(a.out)
    print(json.dumps({"installed":[x["tool_id"] for x in found["actual_installed_tools"]],
        "wired_to_zx7":[x["tool_id"] for x in found["actual_installed_tools"] if x["can_render_in_zx7_now"]],
        "others_available_but_not_integrated":[x["tool_id"] for x in found["actual_installed_tools"] if not x["can_render_in_zx7_now"]],
        "not_installed":[x["tool_id"] for x in found["not_installed_tools"]]},indent=2))


if __name__=="__main__":
    main()
