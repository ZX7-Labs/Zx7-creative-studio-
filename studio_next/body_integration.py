"""Real executable ZX7 body tools for rights-cleared editable media projects.

The artist/model authors original film IR and chooses tools from discovery.
This trusted installed *body* provides reusable FFmpeg, ASWF OpenTimelineIO,
Inkscape design, actual media verification, archive and thumbnails as ops.

No preset scene count, style, transition, aspect ratio, duration, or genre.
No model-supplied Python, arbitrary shell command, network or spend permission.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import os
import uuid
import json
import shutil
import zipfile
from pathlib import Path

from .contracts import ToolSpec
from .creative_research import CreativeResearch
from .registry import ToolCatalog
from .edit_timeline import render_edit,_path_within
from .editorial_interchange import export_editable_timeline
from .body_sequence_otio import export_verified_sequence_otio,import_verified_sequence_otio
from .body_mlt_editor import export_owned_mlt,verify_owned_mlt_project
from .body_mlt_render import render_owned_mlt
from .body_mlt_roundtrip import import_owned_mlt_project
from .body_mlt_revision import revise_owned_mlt_project
from .body_mlt_relink import relink_owned_mlt_project
from .body_mlt_compare import compare_owned_mlt_projects
from .body_timecode import (frame_timecode_receipt,parse_timecode_receipt,
                            verify_timecode_receipt,native_mlt_timecode_receipt,
                            verify_native_timecode_receipt)
from .creative_asset_ops import rasterize_original_svg,extract_director_selected_frame
from .native_body_engines import render_original_blender,render_original_motion
from .body_cgi import render_cgi_plan
from .body_visual_render import render_visual_graph
from .body_visual_document import author_visual_document, read_visual_document
from .body_motion_project import run_motion_project,export_motion_media,verify_motion_bundle,motion_runtime_ready
from .body_planar import render_planar_insert
from .delivery_audit import audit_delivered_movie,_probe_details
from .durable_graph import DurableFilmGraph,execute_durable_film_graph
from .media_vault import MediaVault,sha256_file,verify_media_container,MediaCustodyError
from .composite_mix import render_composition
from .film_finishing import finish_authorized_movie
from .body_color_pipeline import render_verified_color_job
from .body_exr_passes import render_original_exr_passes,verify_exr_bundle
from .body_aces2_preview import render_aces_2_sdr_preview
from .body_aces2_movie import render_aces2_scene_movie
from .body_frame_resume import render_resumable_exr_passes
from .precision_retime import render_retime
from .body_sequence_cuts import render_verified_sequence
from .body_timeline_revision import render_editorial_revision
from .body_owned_edit import render_verified_owned_edit,validate_owned_edit
from .production_qc import full_decode_inspection
from .body_loudness import inspect_original_loudness
from .body_observation import produce_review_bundle,verify_review_bundle
from .body_temporal_evidence import (
    observe_every_original_frame,verify_full_temporal_evidence)
from .body_review_access import read_verified_review,extract_verified_review_frame
from .body_review_compare import compare_verified_revisions
from .body_plugins import discover_enabled_body_plugins
from .body_tool_contracts import real_operation_schema
from .body_materials import fingerprint_physical_inputs
from .generative_video_providers import discover_local_generators
from .comfy_video_runtime import render_actual_generated_scene,validate_video_job
from .body_publication import (publication_record_exists, prepare_publication,
                               recover_publication, sync_published_file,
                               current_trusted_attempt_tool,
                               authorized_publication)


def _body_output(workspace,name,*,allowed=(".mp4",".otio",".png")):
    p=_path_within(workspace,name,exists=False)
    if p.suffix.lower() not in allowed:
        raise ValueError("Destination not a supported actual media artifact")
    if p.exists() and not publication_record_exists(p):
        raise FileExistsError("Do not overwrite existing accepted creative result")
    p.parent.mkdir(parents=True,exist_ok=True)
    return p


def _witness(file):
    f=Path(file)
    if not f.is_file() or f.stat().st_size<100:
        raise ValueError("No genuine digital media file produced")
    digest=sha256_file(f)
    out={"path":str(f.resolve()),"sha256":digest,"bytes":f.stat().st_size}
    if f.suffix.lower() in (".mp4",".mov",".mkv",".webm"):
        meta=_probe_details(f)
        out.update({"duration_seconds":meta["duration_seconds"],
                    "width":meta["width"],"height":meta["height"],
                    "audio_present":meta["audio_stream_present"]})
    elif f.suffix.lower()==".png":
        verify_media_container(f,"image/png")
    elif f.suffix.lower()==".exr":
        verify_media_container(f,"image/x-exr")
    elif f.suffix.lower()==".zip":
        verify_exr_bundle(f)
    elif f.suffix.lower()==".zxreview":
        verify_review_bundle(f)
    elif f.suffix.lower()==".json":
        verify_full_temporal_evidence(f)
    elif f.suffix.lower()==".zxmotion":
        verify_motion_bundle(f)
    elif f.suffix.lower()==".mlt":
        verify_owned_mlt_project(f)
    return out


def _verify_witness(result):
    if not isinstance(result,dict) or "path" not in result or "sha256" not in result:
        return False
    p=Path(result["path"])
    if not p.is_file() or sha256_file(p)!=result["sha256"]:
        return False
    if p.suffix.lower()==".mlt":
        try:return verify_owned_mlt_project(p)["verified_original_sources"]>0
        except (ValueError,OSError,KeyError):return False
    if p.suffix.lower()==".zxmotion":
        try:return bool(verify_motion_bundle(p)["native"])
        except (ValueError,KeyError,OSError,zipfile.BadZipFile):return False
    if p.suffix.lower() in (".mp4",".mov",".mkv",".webm"):
        observed=_probe_details(p)
        return (abs(observed["duration_seconds"]-result["duration_seconds"])<.08
                and observed["audio_stream_present"]==result["audio_present"])
    if p.suffix.lower()==".zip":
        try:
            return bool(verify_exr_bundle(p)["original_exr_passes_real"])
        except (ValueError,RuntimeError,OSError,zipfile.BadZipFile):
            return False
    if p.suffix.lower()==".zxreview":
        try:
            return bool(verify_review_bundle(p)["true_image_decoders_completed"])
        except (ValueError,RuntimeError,OSError,zipfile.BadZipFile):
            return False
    if p.suffix.lower()==".json":
        try:
            return bool(verify_full_temporal_evidence(p)["full_CFR_frame_evidence_valid"])
        except (ValueError,TypeError,KeyError,OSError,RuntimeError):
            return False
    if p.suffix.lower()==".png":
        try:
            verify_media_container(p,"image/png")
            return True
        except (OSError,ValueError,RuntimeError):
            return False
    if p.suffix.lower()==".exr":
        try:
            verify_media_container(p,"image/x-exr")
            return True
        except (OSError,ValueError,RuntimeError):
            return False
    if p.suffix.lower()==".otio":
        try:
            import opentimelineio as otio
            movie=otio.adapters.read_from_file(str(p))
            return len(movie.video_tracks())>0
        except (ImportError,ValueError,RuntimeError,AttributeError):
            return False
    return False


def _trusted_body_revision(tool_id):
    """Per-tool code and installed executable revision, not a fixed schema label.

    Renderer implementation changes invalidate cached creative media only for
    that operation and downstream consumers of its physical output.
    """
    base=Path(__file__).resolve().parent
    dependencies={
        "body.inspect":["delivery_audit.py"],
        "body.timecode_format":["body_timecode.py"],
        "body.timecode_parse":["body_timecode.py"],
        "body.mlt_owned_timecode_format":["body_timecode.py","body_mlt_roundtrip.py","body_mlt_editor.py","pcm_wave.py","media_vault.py"],
        "body.mlt_owned_timecode_parse":["body_timecode.py","body_mlt_roundtrip.py","body_mlt_editor.py","pcm_wave.py","media_vault.py"],
        "body.resolve_asset":["media_vault.py"],
        "body.voice_inventory":["voice_contract.py"],
        "body.render_edit":["edit_timeline.py"],
        "body.render_edit_owned":["body_owned_edit.py","edit_timeline.py","media_vault.py","production_qc.py"],
        "body.retime":["precision_retime.py","media_vault.py","delivery_audit.py","composite_mix.py","production_qc.py"],
        "body.sequence_cuts":["body_sequence_cuts.py","precision_retime.py","media_vault.py","body_color_pipeline.py","composite_mix.py","production_qc.py"],
        "body.timeline_revision":["body_timeline_revision.py","body_sequence_cuts.py","precision_retime.py","media_vault.py","body_color_pipeline.py","composite_mix.py","production_qc.py"],
        "body.otio":["editorial_interchange.py"],
        "body.otio_owned_export":["body_sequence_otio.py","body_sequence_cuts.py","media_vault.py","precision_retime.py","body_color_pipeline.py","composite_mix.py"],
        "body.mlt_owned_export":["body_mlt_editor.py","pcm_wave.py","media_vault.py","precision_retime.py","body_color_pipeline.py","delivery_audit.py","composite_mix.py"],
        "body.mlt_owned_render":["body_mlt_render.py","body_mlt_editor.py","pcm_wave.py","media_vault.py","precision_retime.py","production_qc.py","composite_mix.py"],
        "body.mlt_owned_import":["body_mlt_roundtrip.py","body_mlt_editor.py","body_materials.py","pcm_wave.py","media_vault.py","precision_retime.py","body_color_pipeline.py"],
        "body.mlt_owned_relink":["body_mlt_relink.py","body_asset_links.py","body_mlt_roundtrip.py","body_mlt_editor.py","body_materials.py","media_vault.py","pcm_wave.py","precision_retime.py","body_color_pipeline.py"],
        "body.mlt_owned_compare":["body_mlt_compare.py","body_mlt_roundtrip.py","body_mlt_editor.py","body_materials.py","pcm_wave.py","media_vault.py","precision_retime.py","body_color_pipeline.py"],
        "body.mlt_owned_revision":["body_mlt_revision.py","body_mlt_linked_actions.py","body_mlt_local_edits.py","body_mlt_placements.py","body_project_revision.py","body_mlt_roundtrip.py","body_mlt_editor.py","body_materials.py","pcm_wave.py","media_vault.py","precision_retime.py","body_color_pipeline.py"],
        "body.otio_owned_import":["body_sequence_otio.py","body_sequence_cuts.py","media_vault.py","precision_retime.py","body_color_pipeline.py","composite_mix.py"],
        "body.vector_png":["creative_asset_ops.py"],
        "body.film_thumbnail":["creative_asset_ops.py","delivery_audit.py"],
        "body.asset_vault":["media_vault.py"],
        "body.composite_mix":["composite_mix.py","media_vault.py","production_qc.py"],
        "body.visual_author":["body_visual_document.py","body_visual_graph.py","body_pixel_math.py","media_vault.py"],
        "body.visual_document":["body_visual_document.py","body_visual_graph.py","body_pixel_math.py","media_vault.py"],
        "body.visual_graph":["body_visual_graph.py","body_visual_render.py","body_visual_contract.py","body_visual_exr.py",
                             "body_pixel_math.py","body_animation.py","composite_mix.py","media_vault.py","production_qc.py"],
        "body.motion_project":["body_motion_project.py","body_motion_worker.py"],
        "body.motion_export":["body_motion_project.py","production_qc.py"],
        "body.film_finish":["film_finishing.py","media_vault.py","composite_mix.py","production_qc.py"],
        "body.color_lut":["body_color_pipeline.py","media_vault.py","delivery_audit.py","composite_mix.py","production_qc.py"],
        "body.full_decode":["production_qc.py","delivery_audit.py"],
        "body.loudness":["body_loudness.py","media_vault.py","composite_mix.py"],
        "body.review":["body_observation.py","production_qc.py","media_vault.py"],
        "body.temporal_evidence":["body_temporal_evidence.py","composite_mix.py","precision_retime.py","body_observation.py","production_qc.py","media_vault.py"],
        "body.review_data":["body_review_access.py","body_observation.py"],
        "body.review_frame":["body_review_access.py","body_observation.py"],
        "body.review_compare":["body_review_compare.py","body_review_access.py","body_observation.py"],
        "body.generate_video":["comfy_video_runtime.py","generative_video_providers.py","composite_mix.py","media_vault.py"],
        "body.blender3d":["native_body_engines.py","blender_scene.py"],
        "body.cgi_shot":["body_cgi.py","native_body_engines.py","blender_scene.py","media_vault.py","composite_mix.py","production_qc.py"],
        "body.planar_insert":["body_planar.py","media_vault.py","composite_mix.py","precision_retime.py","body_color_pipeline.py","production_qc.py"],
        "body.exr_passes":["body_exr_passes.py","blender_scene.py","media_vault.py"],
        "body.aces2_preview":["body_aces2_preview.py","body_exr_passes.py","media_vault.py"],
        "body.aces2_movie":["body_aces2_movie.py","body_aces2_preview.py","body_exr_passes.py","media_vault.py","production_qc.py"],
        "body.exr_checkpoint":["body_frame_resume.py","body_exr_passes.py","blender_scene.py","media_vault.py"],
        "body.motion2d":["native_body_engines.py","motion_bridge.py","font_registry.py",
                         "silent_audio.py","voice_contract.py","sound_synthesis.py","../motion_studio/render.py","../motion_studio/voice.py"],
    }
    commands={
        "body.inspect":["ffprobe"],
        "body.timecode_format":[],
        "body.timecode_parse":[],
        "body.mlt_owned_timecode_format":["ffmpeg","ffprobe"],
        "body.mlt_owned_timecode_parse":["ffmpeg","ffprobe"],
        "body.resolve_asset":[],
        "body.voice_inventory":[],
        "body.render_edit":["ffmpeg","ffprobe"],
        "body.render_edit_owned":["ffmpeg","ffprobe"],
        "body.retime":["ffmpeg","ffprobe"],
        "body.sequence_cuts":["ffmpeg","ffprobe"],
        "body.timeline_revision":["ffmpeg","ffprobe"],
        "body.otio":[],
        "body.otio_owned_export":["ffmpeg","ffprobe"],
        "body.mlt_owned_export":["melt","ffmpeg","ffprobe"],
        "body.mlt_owned_render":["melt","ffmpeg","ffprobe"],
        "body.mlt_owned_import":["ffmpeg","ffprobe"],
        "body.mlt_owned_relink":["ffmpeg","ffprobe"],
        "body.mlt_owned_compare":["ffmpeg","ffprobe"],
        "body.mlt_owned_revision":["melt","ffmpeg","ffprobe"],
        "body.otio_owned_import":["ffmpeg","ffprobe"],
        "body.vector_png":["inkscape"],
        "body.film_thumbnail":["ffmpeg","ffprobe"],
        "body.asset_vault":[],
        "body.composite_mix":["ffmpeg","ffprobe"],
        "body.visual_author":[],
        "body.visual_document":[],
        "body.visual_graph":["ffmpeg","ffprobe"],
        "body.motion_project":["blender"],
        "body.motion_export":["ffmpeg","ffprobe"],
        "body.film_finish":["ffmpeg","ffprobe"],
        "body.color_lut":["ffmpeg","ffprobe"],
        "body.full_decode":["ffmpeg","ffprobe"],
        "body.loudness":["ffmpeg","ffprobe"],
        "body.review":["ffmpeg","ffprobe"],
        "body.temporal_evidence":["ffmpeg","ffprobe"],
        "body.review_data":[],
        "body.review_frame":[],
        "body.review_compare":[],
        "body.generate_video":["ffprobe"],
        "body.blender3d":["blender","ffmpeg"],
        "body.cgi_shot":["blender","ffmpeg","ffprobe"],
        "body.planar_insert":["ffmpeg","ffprobe"],
        "body.exr_passes":["blender"],
        "body.aces2_preview":[],
        "body.aces2_movie":["ffmpeg","ffprobe"],
        "body.exr_checkpoint":["blender"],
        "body.motion2d":["ffmpeg","ffprobe"],
    }
    known=dependencies.get(tool_id)
    if known is None:
        raise ValueError("No verified implementation dependencies for "+tool_id)
    if "body_mlt_editor.py" in known:
        # Source geometry and all nine RGB grading curves participate in
        # strict native validation, recovery, rendering and review. A change
        # to either bridge invalidates every affected cached operation.
        known=[*known,"body_mlt_transform.py","body_mlt_grade.py","body_mlt_tone.py"]
    h=hashlib.sha256()
    for item in ("body_integration.py","body_publication.py","durable_sqlite.py",
                 "body_tool_contracts.py","body_document_schemas.py","registry.py")+tuple(known):
        p=base/item
        h.update(item.encode())
        h.update(p.read_bytes())
    for cmd in commands[tool_id]:
        executable=shutil.which(cmd)
        if executable is None:
            raise ValueError("Cannot fingerprint missing actual creative renderer")
        file=Path(executable).resolve()
        stat=file.stat()
        h.update(json.dumps({"command":cmd,"binary_path":str(file),
              "size":stat.st_size,"mtime_ns":stat.st_mtime_ns},sort_keys=True).encode())
    runtime_libraries={"body.planar_insert":("opencv-python-headless","numpy"),
                       "body.visual_graph":("numpy","Pillow","OpenEXR"),
                       "body.motion2d":("numpy","Pillow","fonttools","supertonic"),
                       "body.otio":("opentimelineio",),
                       "body.otio_owned_export":("opentimelineio",),
                       "body.otio_owned_import":("opentimelineio",),
                       "body.review":("Pillow",),
                       "body.temporal_evidence":("numpy",),
                       "body.review_data":("Pillow",),
                       "body.review_frame":("Pillow",),
                       "body.review_compare":("Pillow",),
                       "body.exr_passes":("OpenEXR",),
                       "body.aces2_preview":("OpenEXR","opencolorio","Pillow","numpy"),
                       "body.aces2_movie":("OpenEXR","opencolorio","numpy")}
    for library in runtime_libraries.get(tool_id,()):
        try:version=importlib.metadata.version(library)
        except importlib.metadata.PackageNotFoundError:version="not_installed"
        h.update(json.dumps({"library":library,"version":version},sort_keys=True).encode())
    return "sha256:"+h.hexdigest()


def _commit_actual_body_output(final_path,render):
    """Only expose fully encoded, *decoder verified* original media.

    Incomplete FFmpeg/Blender/graphics files never occupy the final accepted
    filename. An atomic same-filesystem hardlink refuses concurrent
    overwrites instead of clobbering an earlier director-approved result.
    """
    final_path=Path(final_path)
    # Recovery may publish a staged inode. It is also a write and must be
    # fenced to the *current* owner; the receipt identity remains stable.
    with authorized_publication():
        recovered=recover_publication(
            final_path,witness=_witness,verify=_verify_witness)
        if recovered is not None:
            return recovered
        if final_path.exists():
            raise FileExistsError("Cannot overwrite original media output")
    stage=final_path.with_name(
        ".zx7-uncommitted-"+uuid.uuid4().hex+final_path.suffix)
    try:
        # Slow, untrusted renderer work happens outside the SQLite lease
        # transaction. Publication alone holds the short writer fence.
        render(stage)
        preliminary=_witness(stage)
        if not _verify_witness(preliminary):
            raise RuntimeError("Staged creative media failed real decoder validation")
        with authorized_publication():
            # A different verified worker may have published while this
            # renderer ran. Never clobber its final artifact or receipt.
            if final_path.exists():
                recovered=recover_publication(
                    final_path,witness=_witness,verify=_verify_witness)
                if recovered is not None:
                    return recovered
                raise FileExistsError("Cannot overwrite original media output")
            prepare_publication(final_path,stage,preliminary)
            os.link(stage,final_path)
            # The same lease transaction covers the durable receipt,
            # final hardlink and directory fsync; no takeover in between.
            sync_published_file(final_path)
        return _witness(final_path)
    finally:
        # Only our private encoded staging file is ours to remove. A previous
        # hardlink publication has a durable receipt and remains recoverable.
        stage.unlink(missing_ok=True)


def body_catalog(workspace,*,vault_root=None,editor_client=None,research_client=None):
    """Attach native editor operations only through a host-configured client.

    The host owns its grants and argument/path policy. Project/model arguments
    cannot attach an editor or expand grants. Native writes are stateful and
    are never advertised as replayable cached work or media delivery receipts.
    """
    root=Path(workspace).resolve()
    vault=MediaVault(vault_root or (root/"vault"))
    catalog=ToolCatalog()
    # Research cannot become a source-rights attestation or a media writer.
    # Its explicit 'network' permission is not included in ordinary read grants.
    # The caller can attach an independently configured trusted client.
    researcher = research_client if research_client is not None else CreativeResearch()
    for operation_id, description, required, properties, runner in (
        ("body.research_assets",
         "Search CC0 candidate image/audio/video metadata. No download, "
         "no verified license, no automatic source import; original rights review required.",
         ["query", "media"],
         {"query": {"type": "string"}, "media": {"type": "string"},
          "limit": {"type": "integer", "minimum": 1}},
         lambda args: researcher.assets(query=args["query"],media=args["media"],
                                       limit=args.get("limit", 8))),
        ("body.research_studies",
         "Search published scholarly metadata about storytelling, editing, "
         "attention and visual/auditory perception; title is not an audience finding.",
         ["query"],
         {"query": {"type": "string"},
          "limit": {"type": "integer", "minimum": 1}},
         lambda args: researcher.studies(query=args["query"], limit=args.get("limit", 8))),
    ):
        catalog.register(
            ToolSpec(
                operation_id, "creative research evidence",
                description, "network", status="installed",
                license="ZX7 source license; third-party metadata and works retain their own rights",
                resource="free public metadata HTTPS API; no key, scraping or paid runtime",
                operation_schema={"type": "object", "additionalProperties": False,
                                  "required": required, "properties": properties},
                limitations=(
                    "Network grant required; source reachability is checked only on live request.",
                    "Candidate rights are not verified, cleared or imported.",
                    "Model-generated taste or audience claims need independent empirical validation.",
                )),
            runner, idempotent=False)
    video_io=bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
    motion_libraries=all(importlib.util.find_spec(name) is not None
                         for name in ("numpy","PIL","fontTools"))
    png_decoder=bool(importlib.util.find_spec("PIL") is not None or shutil.which("ffmpeg"))

    def add(id,capability,description,access,ready,required,fn,*,idempotent=True):
        catalog.register(ToolSpec(id,capability,description,access,
            status="installed" if ready else "needs_setup",
            license="various installed FOSS or verified asset provenance",
            resource="local machine",
            operation_schema=real_operation_schema(id,required)),fn if ready else None,
            idempotent=idempotent,
            implementation_revision=_trusted_body_revision(id) if ready else None,
            material_fingerprint=(lambda inputs,name=id:
                fingerprint_physical_inputs(name,inputs,root)) if ready else None)

    def format_smpte(inputs):
        return frame_timecode_receipt(inputs["frame_index"],
            inputs["numerator"],inputs["denominator"],inputs["drop_frame"])

    def parse_smpte(inputs):
        return parse_timecode_receipt(inputs["timecode"],
            inputs["numerator"],inputs["denominator"])

    def format_owned_smpte(inputs):
        return native_mlt_timecode_receipt(inputs["edit"],root,
            vault_root=vault.root,frame_index=inputs["frame_index"],
            drop_frame=inputs["drop_frame"])

    def parse_owned_smpte(inputs):
        return native_mlt_timecode_receipt(inputs["edit"],root,
            vault_root=vault.root,timecode=inputs["timecode"])

    def inspect(inputs):
        path=_path_within(root,inputs["source"],exists=True)
        return _witness(path)

    def author_visual(inputs):
        return author_visual_document(
            root, document=inputs["document"], out=inputs["out"],
            base=inputs.get("base"), expected_sha256=inputs.get("expected_sha256"))

    def read_authored_visual(inputs):
        return read_visual_document(root, plan=inputs["plan"])

    def render_visual(inputs):
        plan=_path_within(root,inputs["plan"],exists=True)
        target=_body_output(root,inputs["out"],allowed=(".png",".mov",".exr"))
        return _commit_actual_body_output(target,lambda staged:
            render_visual_graph(plan,root,vault.root,staged))

    def inspect_voices(inputs):
        from .voice_contract import voice_inventory
        directory=_path_within(root,inputs["voice_assets"],exists=False)
        if not directory.is_dir():raise ValueError("Voice assets must be a local model directory")
        return {"model_dir":str(directory),"inventory":voice_inventory(directory),
                "voice_inference_performed":False}

    def resolve_owner_media(inputs):
        """One compact read tool resolves a verified CAS asset by real identity.

        The model neither picks arbitrary paths nor supplies license labels.
        Existing MediaVault rights witnesses are checked on each invocation.
        """
        inspected=vault.inspect(inputs["asset_id"],
                                attestation_id=inputs["attestation_id"])
        permitted=inspected["rights_attestations"][0]
        return {"path":inspected["path"],
                "sha256":inspected["asset_id"],
                "bytes":inspected["size_bytes"],
                "asset_id":inspected["asset_id"],
                "portable_uri":"zx7:sha256:"+inspected["asset_id"],
                "attestation_id":permitted["attestation_id"],
                "rights":permitted["rights"],
                "mime":inspected["mime"]}

    def edit(inputs):
        original=_path_within(root,inputs["edit"],exists=True)
        output=_body_output(root,inputs["out"],allowed=(".mp4",))
        return _commit_actual_body_output(
            output,lambda staged:render_edit(original,root,staged))

    def edit_attested(inputs):
        plan=_path_within(root,inputs["edit"],exists=True)
        target=_body_output(root,inputs["out"],allowed=(".mp4",))
        # Read independent input/source facts even when the output is recovered
        # directly from an atomic crash journal without calling the encoder.
        initial_sha=sha256_file(plan)
        authored=json.loads(plan.read_text(encoding="utf-8"))
        if sha256_file(plan)!=initial_sha:
            raise ValueError("Director cut changed while preflighting original inputs")
        original,source_hashes=validate_owned_edit(authored,root,vault.root)
        verification={}
        def produce(stage):
            if sha256_file(plan)!=initial_sha:
                raise ValueError("Director cut changed before original renderer")
            observed=render_verified_owned_edit(plan,root,vault.root,stage)
            verification.update(observed)
            if observed["plan_sha256"]!=initial_sha:
                raise ValueError("Verified rendering used a different director cut")
        receipt=_commit_actual_body_output(target,produce)
        # Crash recovery may reuse an existing exact movie. It must still
        # fully decode picture and soundtrack before accepting that film.
        if not verification:
            check=full_decode_inspection(target,expected={
                "width":authored["format"]["width"],
                "height":authored["format"]["height"],
                "require_audio":True})
            if not check["technical_delivery_verified"] or not check[
                    "full_picture_and_sound_decoder_completed"]:
                raise RuntimeError("Recovered owner movie failed full physical decode")
        if sha256_file(plan)!=initial_sha or any(
                sha256_file(path)!=digest for path,digest in source_hashes.items()):
            raise ValueError("Original proof changed while recovering or publishing")
        return {**receipt,"source_custody_count":len(original["clips"]),
                "distinct_originals":len(source_hashes),
                "director_plan_sha256":initial_sha,
                "original_footage_unchanged":True,
                "full_picture_and_sound_decoder_completed":True,
                "artistic_quality_certified":False}

    def retime_footage(inputs):
        plan=_path_within(root,inputs['plan'],exists=True)
        target=_body_output(root,inputs['out'],allowed=('.mp4',))
        return _commit_actual_body_output(target,
            lambda staged:render_retime(plan,root,vault.root,staged))

    def cut_owned_picture(inputs):
        plan=_path_within(root,inputs["plan"],exists=True)
        dest=_body_output(root,inputs["out"],allowed=(".mp4",))
        return _commit_actual_body_output(dest,
             lambda stage:render_verified_sequence(plan,root,vault.root,stage))

    def revise_original_film(inputs):
        plan=_path_within(root,inputs["plan"],exists=True)
        operation=_path_within(root,inputs["operation"],exists=True)
        dest=_body_output(root,inputs["out"],allowed=(".mp4",))
        evidence={}
        def encode(stage):
            evidence.update(render_editorial_revision(plan,operation,root,vault.root,stage))
        receipt=_commit_actual_body_output(dest,encode)
        return {**receipt, "revision_plan":evidence["revision_plan"],
                "revision_plan_sha256":evidence["revision_plan_sha256"],
                "prior_plan_sha256":evidence["prior_plan_sha256"],
                "director_operation_sha256":evidence["director_operation_sha256"],
                "operations":evidence["operations"],"reversible_original_media":True}

    def export_edit(inputs):
        original=_path_within(root,inputs["edit"],exists=True)
        output=_body_output(root,inputs["out"],allowed=(".otio",))
        return _commit_actual_body_output(
            output,lambda staged:export_editable_timeline(original,root,staged))

    def export_strict_cut(inputs):
        plan=_path_within(root,inputs["plan"],exists=True)
        out=_body_output(root,inputs["out"],allowed=(".otio",))
        # The original path is an immutable artist plan. The physical OTIO
        # exporter itself proves every camera source, its license, and the
        # synchronized original audio in the actual native roundtrip.
        receipt=_commit_actual_body_output(out,lambda stage:
            export_verified_sequence_otio(plan,root,vault.root,stage))
        decoded=import_verified_sequence_otio(out,root,vault.root)
        authored=json.loads(plan.read_text(encoding="utf-8"))
        if (decoded["source_plan_sha256"]!=sha256_file(plan) or
                len(decoded["plan"]["clips"])!=len(authored["clips"])):
            raise ValueError("Recovered OTIO does not match director-owned edit")
        return {**receipt,
            "verified_original_frames":decoded["frame_count"],
            "original_audio_kept_synchronized":True,
            "full_nle_creative_quality_approved":False}

    def import_strict_cut(inputs):
        edit=_path_within(root,inputs["edit"],exists=True)
        out=_body_output(root,inputs["out"],allowed=(".json",))
        imported=import_verified_sequence_otio(edit,root,vault.root)
        contents=(json.dumps(imported["plan"],sort_keys=True,
                  ensure_ascii=False,separators=(",",":"))+"\n").encode("utf-8")
        if out.exists():raise FileExistsError("Original approved director edit cannot be overwritten")
        temp=out.with_name(".zx7-otio-import-"+uuid.uuid4().hex+".json")
        try:
            with temp.open("xb") as dst:
                dst.write(contents)
                dst.flush()
                os.fsync(dst.fileno())
            if sha256_file(temp)!=hashlib.sha256(contents).hexdigest():
                raise ValueError("Original industry edit changed while publishing")
            os.link(temp,out)
        finally:
            temp.unlink(missing_ok=True)
        return {"path":str(out),"sha256":sha256_file(out),
                "bytes":len(contents),"verified_original_frames":imported["frame_count"],
                "synchronous_sound_source_verified":True,
                "industry_otio_edit_preserved_without_silent_drop":True,
                "creative_quality_approved":False}

    def vector_art(inputs):
        original=_path_within(root,inputs["source_svg"],exists=True)
        output=_body_output(root,inputs["out"],allowed=(".png",))
        return _commit_actual_body_output(
            output,lambda staged:rasterize_original_svg(original,staged,
                width=inputs["width"],height=inputs["height"]))

    def thumbnail(inputs):
        original=_path_within(root,inputs["source_film"],exists=True)
        target=_body_output(root,inputs["out"],allowed=(".png",))
        return _commit_actual_body_output(
            target,lambda staged:extract_director_selected_frame(original,
                staged,at_seconds=inputs["time_seconds"]))

    def composite(inputs):
        source=_path_within(root,inputs["plan"],exists=True)
        out=_body_output(root,inputs["out"],allowed=(".mp4",))
        return _commit_actual_body_output(
            out,lambda staged:render_composition(source,root,vault.root,staged))

    def finish_movie(inputs):
        source=_path_within(root,inputs["plan"],exists=True)
        dest=_body_output(root,inputs["out"],allowed=(".mp4",))
        return _commit_actual_body_output(
            dest,lambda staged:finish_authorized_movie(
                source,root,vault.root,staged))

    def color_grade_movie(inputs):
        plan=_path_within(root,inputs["plan"],exists=True)
        dest=_body_output(root,inputs["out"],allowed=(".mp4",".mov"))
        return _commit_actual_body_output(dest,
             lambda staged:render_verified_color_job(plan,root,vault.root,staged))

    def review_actual_film(inputs):
        original=_path_within(root,inputs["plan"],exists=True)
        dest=_body_output(root,inputs["out"],allowed=(".zxreview",))
        return _commit_actual_body_output(dest,
            lambda staged:produce_review_bundle(original,root,vault.root,staged))

    def temporal_all_frames(inputs):
        original=_path_within(root,inputs["plan"],exists=True)
        dest=_body_output(root,inputs["out"],allowed=(".json",))
        receipt=_commit_actual_body_output(dest,
            lambda staged:observe_every_original_frame(
                original,root,vault.root,staged))
        actual=verify_full_temporal_evidence(dest)
        # On a verified crash-recovery hit the renderer does not run again.
        # Read the existing decoded source-bound evidence, never fabricate a
        # model-visible sound/full-frame status from a stale Python variable.
        return {**receipt,
                "actual_full_movie_frame_count":
                    actual["observed_original_picture_frames"],
                "original_movie_sha256":actual["source_sha256"],
                "original_sound_physically_measured":
                    actual["original_sound_physically_measured"],
                "original_sound_covers_entire_picture":
                    actual["original_sound_covers_entire_picture"],
                "creative_quality_certified":False}

    def aces_review_frame(inputs):
        plan=_path_within(root,inputs["plan"],exists=True)
        output=_body_output(root,inputs["out"],allowed=(".png",))
        return _commit_actual_body_output(output,
            lambda staged:render_aces_2_sdr_preview(
                plan,root,vault.root,staged))

    def aces_native_scene_movie(inputs):
        plan=_path_within(root,inputs["plan"],exists=True)
        output=_body_output(root,inputs["out"],allowed=(".mov",))
        return _commit_actual_body_output(output,
            lambda staged:render_aces2_scene_movie(
                plan,root,vault.root,staged))

    def review_data(inputs):
        archive=_path_within(root,inputs["bundle"],exists=True)
        return read_verified_review(archive,inputs["bundle_sha256"],root)

    def review_compare(inputs):
        prior=_path_within(root,inputs["before_bundle"],exists=True)
        after=_path_within(root,inputs["after_bundle"],exists=True)
        return compare_verified_revisions(prior,inputs["before_sha256"],
                 after,inputs["after_sha256"],root)

    def review_frame(inputs):
        archive=_path_within(root,inputs["bundle"],exists=True)
        output=_body_output(root,inputs["out"],allowed=(".png",))
        return _commit_actual_body_output(output,
            lambda staged:extract_verified_review_frame(
                archive,inputs["bundle_sha256"],root,inputs["frame_index"],staged))

    def physical_audio_loudness(inputs):
        original=_path_within(root,inputs["plan"],exists=True)
        return inspect_original_loudness(original,root,vault.root)

    def deep_media_qc(inputs):
        """Decode every actual video/audio stream, not just inspect metadata."""
        source=_path_within(root,inputs["source"],exists=True)
        report=full_decode_inspection(source,expected=inputs.get("expected"))
        if not report["technical_delivery_verified"]:
            raise RuntimeError("Full original media failed actual decode or director specifications: "+
                               str(report["delivery_mismatches"]))
        # The standard tool-result witness is also rechecked on every restart.
        return report

    def generate_genuine_video(inputs):
        """Only a real approved local GPU model may execute an authored shot.

        The director owns text, frame timing, camera/acting, aspect and seed.
        The model-specific Comfy graph is supplied by audited host installer;
        no raw model Python, web URLs or arbitrary shell commands are allowed.
        """
        source=_path_within(root,inputs["video_job"],exists=True)
        dest=_body_output(root,inputs["out"],allowed=(".mp4",))
        job=validate_video_job(json.loads(source.read_text(encoding="utf-8")))
        local_endpoint=os.getenv("ZX7_COMFY_API")
        local_weights=os.getenv("ZX7_VIDEO_DEPLOYMENTS","models/creative-video")
        from .generative_video_providers import generator_material_identity
        deployment=generator_material_identity(local_weights,job['model_id'])
        stable_sha=hashlib.sha256(source.read_bytes()+json.dumps(
            {'deployment':deployment,'local_endpoint':local_endpoint},sort_keys=True).encode()).hexdigest()[:32]
        physical_job_folder=root/"_real_generated_jobs"/stable_sha
        actual=render_actual_generated_scene(
            job,physical_job_folder,deployment_root=local_weights,
            comfy_endpoint=local_endpoint,workspace=root,vault_root=vault.root)
        filmed=Path(actual["clip"])
        if not filmed.is_file():
            raise RuntimeError("Real video diffusion tool supplied no source footage")
        return _commit_actual_body_output(
            dest,lambda staged:shutil.copyfile(filmed,staged))

    def render_checkpointed_exr(inputs):
        scene=_path_within(root,inputs["scene_json"],exists=True)
        dest=_body_output(root,inputs["out"],allowed=(".zip",))
        evidence=render_resumable_exr_passes(scene,root,dest)
        # Verified zip/physical EXR scene frames, not arbitrary bytes.
        result=_witness(dest)
        if not _verify_witness(result):
            raise ValueError("Rendered EXR stage failed native release verification")
        result.update({"actual_32bit_float_VFX_passes":True,
                       "verified_frame_reuse_count":evidence["verified_frame_reuse_count"],
                       "newly_rendered_frame_count":evidence["newly_rendered_frame_count"],
                       "original_scene_sha256":evidence["original_scene_sha256"],
                       "human_artist_quality_approved":False,
                       "distributed_worker_execution_proven":False})
        return result

    def render3d(inputs):
        source=_path_within(root,inputs["scene_json"],exists=True)
        dest=_body_output(root,inputs["out"],allowed=(".mp4",))
        trusted_asset_root=_path_within(root,inputs["assets_root"],exists=False) if (
            isinstance(inputs.get("assets_root"),str) and inputs["assets_root"]) else None
        return _commit_actual_body_output(
            dest,lambda staged:render_original_blender(
                source,staged,trusted_asset_root=trusted_asset_root))

    def export_native_owned_mlt(inputs):
        source=_path_within(root,inputs["plan"],exists=True)
        dest=_body_output(root,inputs["out"],allowed=(".mlt",))
        return _commit_actual_body_output(dest,
            lambda staged:export_owned_mlt(source,root,vault.root,staged))

    def import_native_owned_mlt(inputs):
        source=_path_within(root,inputs["edit"],exists=True)
        dest=_body_output(root,inputs["out"],allowed=(".json",))
        return import_owned_mlt_project(source,root,vault.root,dest)

    def relink_native_owned_mlt(inputs):
        source=_path_within(root,inputs["edit"],exists=True)
        dest=_body_output(root,inputs["out"],allowed=(".mlt",))
        evidence={}
        def produce(stage):
            evidence.update(relink_owned_mlt_project(source,root,inputs["old_workspace"],stage))
        output=_commit_actual_body_output(dest,produce)
        return {**output,**{k:v for k,v in evidence.items() if k not in ("path","sha256","bytes")}}

    def compare_native_owned_mlt(inputs):
        old=_path_within(root,inputs["before_edit"],exists=True)
        new=_path_within(root,inputs["after_edit"],exists=True)
        return compare_owned_mlt_projects(old,new,root,vault.root,
                                          focus=inputs.get("focus","summary"))

    def revise_native_owned_mlt(inputs):
        prior=_path_within(root,inputs["edit"],exists=True)
        ops=_path_within(root,inputs["operation"],exists=True)
        dest=_body_output(root,inputs["out"],allowed=(".mlt",))
        evidence={}
        def produce(stage):
            evidence.update(revise_owned_mlt_project(prior,ops,root,vault.root,stage))
        output=_commit_actual_body_output(dest,produce)
        return {**output,**{k:v for k,v in evidence.items()
            if k not in ("path","sha256")}}

    def render_native_owned_mlt(inputs):
        source=_path_within(root,inputs["edit"],exists=True)
        dest=_body_output(root,inputs["out"],allowed=(".mp4",))
        gap_color=inputs.get("gap_color")
        evidence={}
        def produce(stage):
            evidence.update(render_owned_mlt(source,root,stage,gap_color=gap_color))
        receipt=_commit_actual_body_output(dest,produce)
        # Preserve measurements from this actual native execution, including
        # disclosed repair of a historical post-mix bus-filter graph. A
        # recovered publication has only its independently decoded witness;
        # do not fabricate fresh execution measurements for that case.
        return {**receipt,**{k:v for k,v in evidence.items()
                if k not in ("path","sha256","bytes")},
                "director_selected_gap_color":gap_color}

    def native_motion(inputs):
        source=_path_within(root,inputs["plan"],exists=True)
        dest=_body_output(root,inputs["out"],allowed=(".zxmotion",))
        receipt=_commit_actual_body_output(dest,lambda staged:run_motion_project(source,root,staged))
        return {**receipt,"native_project_observations":verify_motion_bundle(dest)["native"]}

    def native_motion_export(inputs):
        source=_path_within(root,inputs["bundle"],exists=True)
        dest=_body_output(root,inputs["out"],allowed=(".png",".mp4"))
        return _commit_actual_body_output(dest,lambda staged:export_motion_media(source,staged,fps=inputs["fps"]))

    def cgi_shot(inputs):
        plan=_path_within(root,inputs["plan"],exists=True)
        dest=_body_output(root,inputs["out"],allowed=(".mp4",))
        measured={}
        def produce(stage):measured.update(render_cgi_plan(plan,root,vault.root,stage))
        receipt=_commit_actual_body_output(dest,produce)
        return {**receipt,**{k:v for k,v in measured.items() if k not in ("path","sha256")},
                "native_controls_observed_in_this_invocation":bool(measured)}

    def planar_insert(inputs):
        plan=_path_within(root,inputs["plan"],exists=True)
        dest=_body_output(root,inputs["out"],allowed=(".mp4",))
        measured={}
        def produce(stage):measured.update(render_planar_insert(plan,root,vault.root,stage))
        receipt=_commit_actual_body_output(dest,produce)
        return {**receipt,**{k:v for k,v in measured.items() if k not in ("path","sha256")},
                "tracking_metrics_observed_in_this_invocation":bool(measured)}

    def render_scene_linear_exr(inputs):
        scene=_path_within(root,inputs["scene_json"],exists=True)
        dest=_body_output(root,inputs["out"],allowed=(".zip",))
        asset_root=_path_within(root,inputs["assets_root"],exists=False) if (
            isinstance(inputs.get("assets_root"),str) and inputs["assets_root"]) else None
        return _commit_actual_body_output(dest,lambda staged:
            render_original_exr_passes(scene,root,staged,assets_root=asset_root))

    def render2d(inputs):
        source=_path_within(root,inputs["original_film_ir"],exists=True)
        dest=_body_output(root,inputs["out"],allowed=(".mp4",))
        voice_root=_path_within(root,inputs["voice_assets"],exists=False) if (
            isinstance(inputs.get("voice_assets"),str) and inputs["voice_assets"]) else None
        return _commit_actual_body_output(
            dest,lambda staged:render_original_motion(source,staged,
                width=inputs["width"],fps=inputs["fps"],
                trusted_voice_assets=voice_root))

    def vault_asset(inputs):
        """Only a validated output from an actually installed production node.

        Model text cannot assert that an arbitrary web image or private file
        has owner-supplied/generated/legal rights. This operation admits only
        graph-bound, physically decoded output of a trusted registered maker.
        Other rights classes require an authenticated external ingestion API.
        """
        if not isinstance(inputs,dict) or set(inputs)!={"source_witness"}:
            raise ValueError("Generated media custody requires only a trusted producer output")
        if current_trusted_attempt_tool()!="body.asset_vault":
            raise PermissionError("Only the verified durable producer DAG may issue generated-media provenance")
        proof=inputs["source_witness"]
        if not _verify_witness(proof):
            raise ValueError("No physically proven producer output for media custody")
        source=Path(proof["path"]).resolve()
        if not source.is_relative_to(root):
            raise ValueError("Only genuine media from this original workspace")
        supported={".mp4":"video/mp4",".png":"image/png",".exr":"image/x-exr",
                   ".mov":"video/quicktime",".webm":"video/webm",
                   ".zip":"application/x-zx7-exr-bundle"}
        mime=supported.get(source.suffix.lower())
        if mime is None:
            raise ValueError("Unrecognized verified tool output cannot be laundered into licensed media")
        ref=vault.ingest(source,mime=mime,rights="generated_original",
                  source_type="trusted_renderer",source_id=proof["sha256"],
                  evidence="Verified original media from a registered trusted executable",
                  owner_or_generator="zx7-authorized-body-graph")
        record=vault.inspect(ref["asset_id"],attestation_id=ref["attestation_id"])
        return {"path":record["path"],"sha256":ref["asset_id"],
                "asset_id":ref["asset_id"],"attestation_id":ref["attestation_id"],
                "rights":ref["rights"]}

    # This is a dormant native capability until REAL local GPU, licensed
    # checkpoint components and a live self-hosted graph are verified.
    # A model is never told it can make cinematic live-action from CPU-only tools.
    endpoint=os.getenv("ZX7_COMFY_API")
    available=discover_local_generators(
        comfy_endpoint=endpoint,
        deployed_root=os.getenv("ZX7_VIDEO_DEPLOYMENTS","models/creative-video"))
    native_video_ready=bool(shutil.which("ffprobe") and any(
        x["ready_for_independent_execution_trial"]
        for x in available["video_generation_options"]))
    add("body.generate_video","actual self-hosted text-to-video cinematography",
        "Director-authored actor/camera/action prompt executed by locally verified GPU diffusion model",
        "write",native_video_ready,["video_job","out"],
        generate_genuine_video,idempotent=False)
    add("body.review_compare","physically compare actual original film picture and audio revision evidence",
        "SHA verified matching native decoded PNG timecodes and observed dBFS windows; no fake artist score",
        "read",bool(importlib.util.find_spec("PIL") is not None),
        ["before_bundle","before_sha256","after_bundle","after_sha256"],review_compare)
    add("body.review_data","read actual original film picture and soundtrack review measurements",
        "Trusted decoder-validated source/timestamp/pixel/audio evidence; no invented creative judgement",
        "read",bool(importlib.util.find_spec("PIL") is not None),
        ["bundle","bundle_sha256"],review_data)
    add("body.review_frame","extract one actually decoded original film review picture",
        "Only exact SHA256-bound review archives and selected original PNG frames allowed",
        "write",bool(importlib.util.find_spec("PIL") is not None),
        ["bundle","bundle_sha256","frame_index","out"],review_frame)
    add("body.review","actual original movie picture+sound observations for creative revision",
        "Fully decoded licensed original; director-selected PNG frames, image differences, audio-window dBFS and SHA-bound portable review package",
        "write",bool(shutil.which("ffmpeg") and shutil.which("ffprobe") and
                     importlib.util.find_spec("PIL") is not None),
        ["plan","out"],review_actual_film)
    add("body.temporal_evidence","whole original film frame-by-frame physical evidence",
        "Rights-attested native exact-CFR every-frame RGB metrics and actually decoded soundtrack; no inferred scene meaning",
        "write",bool(shutil.which("ffmpeg") and shutil.which("ffprobe")
                     and importlib.util.find_spec("numpy") is not None),
        ["plan","out"],temporal_all_frames)
    add("body.loudness","measure actual first soundtrack LUFS, LRA and measured true-peak",
        "Read-only native FFmpeg EBU R128 measurement of original rights-cleared movie, no forced mastering targets",
        "read",bool(shutil.which("ffmpeg") and shutil.which("ffprobe")),
        ["plan"],physical_audio_loudness)
    add("body.full_decode","physical full-movie delivery quality assurance",
        "Actually decode entire picture/sound; preserve deliberate creative style",
        "read",bool(shutil.which("ffmpeg") and shutil.which("ffprobe")),
        ["source"],deep_media_qc)
    add("body.color_lut","original licensed 3D color LUT and protected soundtrack",
        "Live FFmpeg exact BT.709 3D-CUBE transform; 8-bit viewing or 10-bit ProRes master",
        "write",video_io,["plan","out"],color_grade_movie)
    add("body.film_finish","measured film color grade and sound finishing",
        "Local FFmpeg real picture operations and original audio loudness mastering",
        "write",bool(shutil.which("ffmpeg") and shutil.which("ffprobe")),
        ["plan","out"],finish_movie)
    add("body.composite_mix","original timeline multilayer edit, licensed voices and audio mix",
        "Actual physical rights-verified layered FFmpeg compositor from model-owned canvas",
        "write",bool(shutil.which("ffmpeg") and shutil.which("ffprobe")),
        ["plan","out"],composite)
    add("body.visual_author","author original editable native photo/motion/VFX graph",
        "Create a fully model-authored source-validated visual graph with bounded expression/math, exact existing-source rights and atomic no-overwrite revision ancestry in one owner workspace; accepts complete native graph data, never executable Python",
        "write",True,["document","out"],author_visual,idempotent=False)
    add("body.visual_document","read exact editable source for selective artistic revision",
        "Read only an owner-owned source graph from private creative-graphs/, with SHA and complete authored node/curve data for new non-destructive revisions; no arbitrary owner JSON or executable file read",
        "read",True,["plan"],read_authored_visual)
    add("body.visual_graph","editable native photo, motion graphic and VFX pixel graph",
        "Authored mathematical pixels, masks, original-frame curves, inverse spatial sampling, convolution and alpha compositing; "
        "float32 linear-sRGB internals, sealed sources, exact RGBA PNG/MOV or float32 EXR (requires OpenEXR 3.3+); separate editable audio",
        "write",bool(video_io and all(importlib.util.find_spec(name) is not None for name in ("numpy","PIL"))),
        ["plan","out"],render_visual)
    add("body.exr_checkpoint","durable original-frame 32float VFX render and exact verified resume",
        "Original Blender Cycles CPU shot with per-frame EXR hash+decoder checkpoints; never a GPU farm",
        "write",bool(shutil.which("blender") and
                      importlib.util.find_spec("OpenEXR") is not None),
        ["scene_json","out"],render_checkpointed_exr)
    add("body.aces2_movie","actual owned ACES2 scene-linear EXR to 10bit SDR movie",
        "Every licensed native RGBA frame receives pinned OCIO2.5 ACES2 view on 16-bit RGB and real ProRes422 10bit encoding; SDR VFX review without audio, not HDR or aesthetic certification",
        "write",bool(shutil.which("ffmpeg") and shutil.which("ffprobe") and
                     importlib.util.find_spec("OpenEXR") and
                     importlib.util.find_spec("PyOpenColorIO") and
                     importlib.util.find_spec("numpy")),
        ["plan","out"],aces_native_scene_movie)
    add("body.aces2_preview","pinned ASWF ACES 2.0 scene-linear to SDR review",
        "Actual OpenEXR float RGBA, rights-attested source, built-in OCIO 2.5 ACES2 display view and independently decoded PNG; review only",
        "write",bool(importlib.util.find_spec("OpenEXR") and
                     importlib.util.find_spec("PyOpenColorIO") and
                     importlib.util.find_spec("PIL") and
                     importlib.util.find_spec("numpy")),
        ["plan","out"],aces_review_frame)
    add("body.exr_passes","real 32bit scene-linear multilayer 3D VFX passes",
        "Blender Cycles CPU verified RGBA/depth/vector/normal EXR frames in immutable bundle",
        "write",bool(shutil.which("blender") and
                      importlib.util.find_spec("OpenEXR") is not None),
        ["scene_json","out"],render_scene_linear_exr)
    add("body.blender3d","physical 3D filmmaking","Blender real rendered geometries, materials and moving camera",
        "write",bool(shutil.which("blender") and video_io),
        ["scene_json","out"],render3d)
    add("body.motion_project","native Blender motion-design project and RNA controls",
        "Isolated native .blend transactions: discover installed properties/enums, create/edit geometry, text, materials, nodes, cameras and animation; "
        "save/reopen immutable packed projects and render authored original frames. Blender 4.5+ required; no full-studio quality certification.",
        "write",motion_runtime_ready(),["plan","out"],native_motion)
    add("body.motion_export","deliver actual native motion project renders",
        "Decode-verified PNG or H264 MP4 from the authored native PNG frame order and explicit integer delivery fps; picture-only export",
        "write",video_io,["bundle","out","fps"],native_motion_export)
    add("body.cgi_shot","source-attested original CGI and native simulation",
        "Sealed texture/GLB assets; PBR, optics, authored shutter, rigid bodies, cloth/pins/collisions, topology-preserving shape keys and native liquid mesh baking (Blender 4.5+); original-clock simulation; Cycles CPU",
        "write",bool(shutil.which("blender") and video_io),["plan","out"],cgi_shot)
    add("body.planar_insert","measured planar tracking and corner-pin VFX",
        "SIFT/RANSAC original reference-to-frame motion; premultiplied-alpha perspective insertion, owned foreground mattes and bitstream-preserved sound; fails on track loss, not 3D camera solve",
        "write",bool(video_io and importlib.util.find_spec("cv2") and importlib.util.find_spec("numpy")),
        ["plan","out"],planar_insert)
    add("body.motion2d","original 2D/2.5D animation","Independent vector character and motion compositor",
        "write",bool(video_io and motion_libraries),["original_film_ir","out","width","fps"],render2d)
    add("body.resolve_asset","verify and locate original licensed media by content identity",
        "Reads actual SHA256 CAS blob and its exact stored owner license attestation",
        "read",True,["asset_id","attestation_id"],resolve_owner_media)
    add("body.timecode_format","exact original-frame SMPTE editorial timecode",
        "Convert a caller-authored exact rational source frame address to a reversible SMPTE label. Distinguish nondrop from supported 30000/1001 and 60000/1001 drop-frame; only numbered labels are skipped, no media frames removed or retimed.",
        "read",True,["numerator","denominator","frame_index","drop_frame"],
        format_smpte)
    add("body.timecode_parse","verify original SMPTE timecode frame address",
        "Parse exact director-supplied HH:MM:SS:FF or HH:MM:SS;FF into a real frame index and rational elapsed clock; reject nonexistent skipped labels, all invented time bases and overflowing 24h epochs.",
        "read",True,["numerator","denominator","timecode"],parse_smpte)
    add("body.mlt_owned_timecode_format","verified original native film timecode",
        "Read actual source-attested editable MLT media and its measured rational FPS; convert one physically available editor frame index to authentic SMPTE timecode, with caller-chosen drop-label policy and no inferred FPS, content changes or media release claims.",
        "read",video_io,["edit","frame_index","drop_frame"],format_owned_smpte)
    add("body.mlt_owned_timecode_parse","verified native film timecode to original frame",
        "Read an exact rights-verified original native MLT project, recover its actual rational FPS, and resolve an independently authored timecode label to an original frame inside the film; reject nonexistent skipped labels and edits beyond physical source frames.",
        "read",video_io,["edit","timecode"],parse_owned_smpte)
    add("body.inspect","measure physical media","FFprobe validates actual source video",
        "read",bool(shutil.which("ffprobe")),["source"],inspect)
    add("body.render_edit","legacy editorial timeline (unattested rights label)",
        "Legacy technical rendering only: a plan's rights string is NOT custody evidence. Use body.render_edit_owned for attested source footage.",
        "write",video_io,["edit","out"],edit)
    add("body.render_edit_owned","source-attested independent mixed-source editing",
        "Exact existing MediaVault content and owner-license attestation for every clip, original fit/fill and independent source sound, physically rendered and verified",
        "write",video_io,["edit","out"],edit_attested)
    add("body.sequence_cuts","precise multishot original rights-attested picture and audio edit",
        "Real verified BT.709 CFR sources, original frame spans, independent sound custody, no unlicensed guessed footage",
        "write",video_io,["plan","out"],cut_owned_picture)
    add("body.timeline_revision","independent exact-frame professional NLE cut modifications",
        "Original rights-verified ripple trim, roll, slip, slide, split and reorder; immutable history; encoded source sound",
        "write",video_io,["plan","operation","out"],revise_original_film)
    add("body.retime","frame-accurate retime and soundtrack sync",
        "Original frame-index speed changes; real rights-checked source and pitch-preserving sound",
        "write",video_io,["plan","out"],retime_footage)
    try:import opentimelineio
    except ImportError:otio_ready=False
    else:otio_ready=True
    add("body.otio","legacy editable edit interchange (unattested source labels)",
        "OpenTimelineIO technical interchange; source license labels are NOT independent custody proof",
        "write",bool(otio_ready and shutil.which("ffprobe")),["edit","out"],export_edit)
    add("body.otio_owned_export","exact-frame source-attested audiovisual OTIO export",
        "Original licensed CFR BT.709 picture and independently synchronized sound, real native OTIO roundtrip verified",
        "write",bool(otio_ready and video_io),["plan","out"],export_strict_cut)
    add("body.otio_owned_import","physically verified original audiovisual OTIO revision import",
        "Strict professional edited OTIO into immutable new JSON director-cut plan; rejects lost/relinked audio/rights",
        "write",bool(otio_ready and video_io),["edit","out"],import_strict_cut)
    add("body.mlt_owned_export","native MLT multi-track editable video-layer project",
        "Rights-attested video overlays, exact CFR in/out and gaps, native track blend and frame-keyframed opacity through measured MLT Cairo compositing. "
        "Upper-layer pixel rectangles, centered fit/distort and rotation with authored film-frame animation before blending; reversible native geometry controls. "
        "Animated source-space rounded-rectangle alpha windows before geometry; transparent outside and fully reversible native masks. "
        "Editable source-attested original video and WAV sound; independently authored dB gain, plus native stereo balance 0-left/0.5-center/1-right and frame-animated position on individual sound buses. All actual volume/panner plugins checked; not full NLE certification.",
        "write",bool(shutil.which("melt") and video_io),["plan","out"],export_native_owned_mlt)
    add("body.mlt_owned_import","reversible rights-attested native MLT timeline to typed edit plan",
        "Reinspect exact original picture/sound rights and rational clock, native layer geometry/rotation, opacity, original-source gain and animated stereo balance; require complete lossless XML roundtrip. Publish immutable edit JSON and reject unsupported native plugins without loss.",
        "write",video_io,["edit","out"],import_native_owned_mlt)
    add("body.mlt_owned_relink","restore native MLT media links after verified workspace relocation",
        "Rebind exact original picture/audio CAS and attestation identities on the new host; verify native effects, timing and lossless roundtrip. Preserve archived original bytes; never open old-host sources or reuse old execution receipts.",
        "write",video_io,["edit","old_workspace","out"],relink_native_owned_mlt)
    add("body.mlt_owned_compare","source-exact visual and soundtrack timeline revision evidence",
        "Read and reattest both original native MLT projects, then obtain a compact summary (default), a precise picture:N or sound:N track, or an explicitly requested all-track source-frame/clip/effect review. Always use exact native roundtrip and rights; never infer pixel equivalence or artistic quality from graph structure.",
        "read",video_io,["before_edit","after_edit"],compare_native_owned_mlt)
    add("body.mlt_owned_revision","non-destructive native MLT multitrack visual and sound revision",
        "Execute source-attested JSON patches, linked razor/ripple, signed-frame roll/slip/slide, or atomic cross-track picture/sound placements with explicit effect policy. Retain author-controlled original sound gain, spatial stereo position, opacity and animation. Prove original rights, source/frame clocks, exact native XML roundtrip and immutable publication. No complete NLE claim.",
        "write",bool(shutil.which("melt") and video_io),["edit","operation","out"],revise_native_owned_mlt)
    add("body.mlt_owned_render","native MLT multitrack audiovisual MP4 rendering",
        "Render fully rights-verified native MLT original picture and audio with exact rational clock; "
        "if all picture tracks are blank, the creative brain must supply an explicit RGB gap_color "
        "to prevent an unapproved white MLT test card. A true decoded frame is compared to the author-selected color.",
        "write",bool(shutil.which("melt") and video_io),["edit","out"],render_native_owned_mlt)
    add("body.vector_png","original vector art and thumbnail","Inkscape headless real vector to PNG",
        "write",bool(shutil.which("inkscape") and png_decoder),["source_svg","out","width","height"],vector_art)
    add("body.film_thumbnail","original movie frame artwork","FFmpeg decode actual selected frame",
        "write",video_io,["source_film","out","time_seconds"],thumbnail)
    add("body.asset_vault","audited generated-media provenance",
        "Custody is accepted only from an actually verified trusted renderer node",
        "write",True,["source_witness"],vault_asset)
    add("body.voice_inventory","discover installed voice identities and synthesis controls",
        "Local style documents and package presence; actual TTS loading remains independently required",
        "read",True,["voice_assets"],inspect_voices)
    if editor_client is not None:
        native={tool["name"]:tool for tool in editor_client.list_tools()}
        if set(editor_client.allowed_tools)-set(native):
            raise ValueError("Host-granted native editor tool is absent from discovery")
        for name,access in editor_client.allowed_tools.items():
            tool=native[name]
            # Keep the native schema intact: BODY's minimal validator must not
            # flatten or reinterpret the editor's richer JSON Schema dialect.
            schema={"type":"object","additionalProperties":False,
                    "required":["arguments"],
                    "properties":{"arguments":tool["inputSchema"]}}
            spec=ToolSpec("body.editor."+name,"native video editor",
                tool.get("description") or name,access,
                license="native editor license; Velorn GPL-3.0-only",
                resource="independently running local editor",
                operation_schema=schema,
                limitations=("Host-granted native operation; not a verified media delivery receipt.",
                             "Stateful writes are not automatically retried or cached."))
            catalog.register(spec,
                lambda inputs,n=name,a=access:editor_client.call(
                    n,inputs["arguments"],
                    # Source introspection is an internal safety prerequisite,
                    # not an additional tool that a model may grant itself.
                    # Other write tools keep their existing exact access.
                    allowed_access=(frozenset({a,"read"}) if n=="split_clip"
                                    else frozenset({a}))),
                idempotent=False)
    for spec,runner,idempotent,version,operational,materials in discover_enabled_body_plugins():
        if not operational:
            from dataclasses import replace
            spec=replace(spec,status="needs_setup")
        catalog.register(spec,runner,idempotent=idempotent,
                         implementation_revision=version if operational else None,
                         material_fingerprint=materials if operational else None)
    return catalog


def validate_witness(_tool_id,result):
    """Physically revisit file and stored rights evidence on every resume."""
    if not isinstance(result,dict):
        return False
    if _tool_id in ("body.timecode_format","body.timecode_parse"):
        return verify_timecode_receipt(result,_tool_id)
    if _tool_id in ("body.mlt_owned_timecode_format","body.mlt_owned_timecode_parse"):
        return verify_native_timecode_receipt(result,_tool_id)
    if _tool_id=="body.mlt_owned_compare":
        # A read-only observation has no exported artifact to hash. Recompute
        # the complete rights-attested native source/frame/effect comparison
        # from both IMMUTABLE physical projects on every durable resume.
        # Never accept a model-authored boolean or stale tool receipt as proof.
        try:
            workspace=Path(result["workspace_root"])
            vault_root=Path(result["media_vault_root"])
            prior=Path(result["before_edit_path"])
            after=Path(result["after_edit_path"])
            if (not workspace.is_absolute() or workspace.is_symlink() or
                    workspace.resolve()!=workspace or
                    vault_root!=workspace/"vault" or
                    not prior.is_relative_to(workspace) or
                    not after.is_relative_to(workspace)):
                return False
            actual=compare_owned_mlt_projects(prior,after,workspace,vault_root,
                                               focus=result["query_focus"])
            return actual==result
        except (ValueError,KeyError,TypeError,OSError,OverflowError):
            return False
    if _tool_id=="body.voice_inventory":
        from .voice_contract import voice_inventory
        try:return result["inventory"]==voice_inventory(result["model_dir"])
        except (ValueError,KeyError,OSError,TypeError):return False
    if "asset_id" in result:
        digest=result.get("asset_id")
        att=result.get("attestation_id")
        if not isinstance(att,str) or digest!=result.get("sha256"):
            return False
        p=Path(result.get("path",""))
        if p.name!=digest or len(p.parents)<3:
            return False
        try:
            # CAS file has no extension because its name is a content digest.
            # Instead of trusting a model's mime, verify SQLite rights custody.
            vault=MediaVault(p.parents[2])
            stored=vault.inspect(digest,attestation_id=att)
            return (Path(stored["path"]).resolve()==p.resolve()
                    and stored["rights_attestations"][0]["rights"]==result.get("rights"))
        except (ValueError,IndexError,OSError):
            return False
    return _verify_witness(result)


def _require_authentic_generated_media_lineage(film_ir):
    """Reject model-supplied rights labels and fake producer objects up front."""
    graph=film_ir.get("tool_graph",[]) if isinstance(film_ir,dict) else []
    if not isinstance(graph,list):
        raise ValueError("Real body graph required for custody validation")
    node_by_id={n["id"]:n for n in graph if isinstance(n,dict) and isinstance(n.get("id"),str)}
    # A legacy rights label, raw SVG, or extracted image cannot manufacture
    # generated-original rights. Only trusted originating renderers or editors
    # which themselves require MediaVault source custody may be archived.
    trusted_producers={"body.blender3d","body.motion2d","body.visual_graph","body.motion_export",
                       "body.exr_passes","body.exr_checkpoint",
                       "body.aces2_movie",
                       "body.render_edit_owned",
                       "body.composite_mix","body.film_finish","body.cgi_shot","body.planar_insert"}
    for node in graph:
        if not isinstance(node,dict) or node.get("tool_id")!="body.asset_vault":
            continue
        inputs=node.get("inputs")
        refs=node.get("depends_on",[])
        if not isinstance(inputs,dict) or set(inputs)!={"source_witness"} or (
                not isinstance(refs,list) or len(refs)!=1 or refs[0] not in node_by_id or
                node_by_id[refs[0]].get("tool_id") not in trusted_producers or
                inputs["source_witness"]!={"$node_output":refs[0]}):
            raise ValueError("LLM cannot invent license/source claims; vault requires exact trusted renderer dependency")


def run_body_project(film_ir,workspace,*,db_name="production.sqlite3",boundary_control=None):
    _require_authentic_generated_media_lineage(film_ir)
    root=Path(workspace)
    catalog=body_catalog(root)
    store=DurableFilmGraph(root/db_name)
    actual_versions=catalog.committed_tool_revisions()
    idempotent=catalog.trusted_idempotent_ids()
    return execute_durable_film_graph(
       film_ir,catalog,fact_ids=set(film_ir.get("owner_facts",{})),
       store=store,output_verifier=validate_witness,
       trusted_idempotent_tools=idempotent,
       tool_revisions=actual_versions,
       input_material_fingerprint=catalog.trusted_material_fingerprint,
       boundary_control=boundary_control,
       allowed_access={"read","write"})


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project",type=Path,required=True)
    p.add_argument("--workspace",type=Path,required=True)
    a=p.parse_args()
    state=run_body_project(json.loads(a.project.read_text()),a.workspace)
    print(json.dumps(state,ensure_ascii=False,indent=2))
    if state["status"]!="all_tool_results_verified":
        raise SystemExit("Production body graph blocked or failed: "+str(state["errors"]))


if __name__=="__main__":main()
