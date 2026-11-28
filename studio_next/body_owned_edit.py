"""An independently rights-attested use of the existing mixed-source FFmpeg editor.

Unlike legacy body.render_edit, no owner/model-provided 'rights' label is
accepted as source custody. Every actual input is bound to an immutable
MediaVault blob and the *exact* attestation, before and after real encoding.
No changes to the original director cut, frame choices, source or soundtrack.
This remains a fit/fill sequential-cut adapter, not a full NLE.
"""
from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .edit_timeline import validate_edit, edit_ffmpeg_command, probe_media, _path_within
from .media_vault import MediaVault, sha256_file, canonical_source_attestations
from .production_qc import full_decode_inspection
from .composite_mix import _decoded_source_duration


def validate_owned_edit(plan, workspace, vault_root):
    """Return a plain editor plan and frozen source identities; no write."""
    root=Path(workspace).resolve()
    if not isinstance(plan,dict) or set(plan)!={"format","clips"} or (
            not isinstance(plan["clips"],list) or not 1<=len(plan["clips"])<=128):
        raise ValueError("Source-attested original edit needs a bounded director timeline")
    vault=MediaVault(vault_root)
    cleaned=copy.deepcopy(plan)
    originals={}
    for index,clip in enumerate(plan["clips"]):
        if not isinstance(clip,dict) or set(clip)!={
                "id","source","rights","audio","asset_id","attestation_id"}:
            raise ValueError(f"Source-attested clip {index} lacks custody")
        cleaned["clips"][index].pop("asset_id")
        cleaned["clips"][index].pop("attestation_id")
        if not isinstance(clip["asset_id"],str) or not isinstance(clip["attestation_id"],str):
            raise ValueError("Original input needs exact content digest and attestation")
        file=_path_within(root,clip["source"],exists=True)
        if (root/clip["source"]).is_symlink():
            raise ValueError("Linked original shot is not trusted")
        observed=vault.inspect(clip["asset_id"],attestation_id=clip["attestation_id"])
        proofs=observed["rights_attestations"]
        if (observed["mime"] not in ("video/mp4","video/quicktime","video/webm") or
                len(proofs)!=1 or proofs[0]["rights"]!=clip["rights"]):
            raise ValueError("Original editor source rights or type differ from stored evidence")
        if sha256_file(file)!=clip["asset_id"]:
            raise ValueError("Original frame source differs from stored content")
        originals[str(file)]=clip["asset_id"]
    validate_edit(cleaned,root)
    return cleaned,originals



def _seal_original_sources(clean, authorized, root, vault_root, private_directory):
    """Privately copy verified immutable CAS sources for one physical encode.

    The editor must consume these frozen bytes, not a mutable working path.
    A caller who changes and restores the working file during FFmpeg must not
    alter decoded frames without changing the approved source digest.
    """
    sealed=copy.deepcopy(clean)
    vault=MediaVault(vault_root)
    pinned={}
    for index,clip in enumerate(authorized["clips"]):
        digest=clip["asset_id"]
        attestation=clip["attestation_id"]
        stored=vault.inspect(digest,attestation_id=attestation)
        suffix=Path(clip["source"]).suffix.lower()
        if suffix not in (".mp4",".mov",".webm",".mkv"):
            raise ValueError("Original video must have an explicitly supported file container")
        identity=(digest,suffix)
        target=pinned.get(identity)
        if target is None:
            target=private_directory/(digest+suffix)
            # A private 0700 directory and read-only private copy ensure the
            # encoder never follows editable source paths or network URLs.
            with Path(stored["path"]).open("rb") as source, target.open("xb") as handle:
                shutil.copyfileobj(source,handle,1024*1024)
                handle.flush()
                os.fsync(handle.fileno())
            if sha256_file(target)!=digest:
                raise ValueError("Verified immutable footage changed during source sealing")
            os.chmod(target,0o400)
            pinned[identity]=target
        sealed["clips"][index]["source"]=str(target.relative_to(root))
    validate_edit(sealed,root)
    return sealed,pinned

def render_verified_owned_edit(plan_file, workspace, vault_root, output):
    root=Path(workspace).resolve()
    plan_file=Path(plan_file).resolve()
    output=Path(output).resolve()
    if (not plan_file.is_relative_to(root) or not plan_file.is_file() or
            plan_file.is_symlink() or not output.is_relative_to(root)
            or output.suffix.lower()!=".mp4" or output.exists()):
        raise ValueError("Original editor needs owner-controlled plan and new MP4")
    before=sha256_file(plan_file)
    plan=json.loads(plan_file.read_text(encoding="utf-8"))
    if sha256_file(plan_file)!=before:
        raise ValueError("Original editor plan changed before custody inspection")
    clean,originals=validate_owned_edit(plan,root,vault_root)
    output.parent.mkdir(parents=True,exist_ok=True)
    try:
        # The original workspace path is checked for custody, but NOT passed
        # to the native decoder. Only locally sealed original CAS bytes may
        # become actual FFmpeg inputs during this transaction.
        with tempfile.TemporaryDirectory(prefix=".zx7-owned-sources-",dir=root) as directory:
            frozen,pinned=_seal_original_sources(
                clean,plan,root,vault_root,Path(directory))
            sources=[probe_media(_path_within(root,c["source"],exists=True))
                     for c in frozen["clips"]]
            # A container or existence-of-audio flag does not prove that
            # recorded dialogue spans its full picture. Reject impossible
            # "preserve original sound" promises before invoking FFmpeg apad.
            for authored in frozen["clips"]:
                if authored["audio"]=="preserve_source":
                    origin=_path_within(root,authored["source"],exists=True)
                    picture_seconds=_decoded_source_duration(origin,"video")
                    sound_seconds=_decoded_source_duration(origin,"audio")
                    if sound_seconds+.015<picture_seconds:
                        raise ValueError(
                            "Original recorded soundtrack ends before the picture; "
                            "cannot pretend missing sound was preserved")
            if sha256_file(plan_file)!=before or any(
                    sha256_file(path)!=digest for path,digest in originals.items()):
                raise ValueError("Original source or plan changed before the actual encoder")
            # FFmpeg -y may only touch an isolated private staging file.
            # Publishing directly to a public destination permits a racing
            # writer's accepted master to be overwritten or deleted on error.
            staged=Path(directory)/"native-owned-edited.mp4"
            command=edit_ffmpeg_command(frozen,root,staged,source_info=sources)
            # No arbitrary owner/model shell commands or mutable source paths.
            complete=subprocess.run(command,capture_output=True,text=True,timeout=3600)
            if complete.returncode:
                raise RuntimeError("Source-attested native editor failed: "+complete.stderr[-1400:])
            final=probe_media(staged)
            if not final["audio"]:
                raise RuntimeError("Encoded film lacks independently decoded soundtrack")
            qa=full_decode_inspection(staged,expected={
                "width":plan["format"]["width"],
                "height":plan["format"]["height"],
                "require_audio":True})
            if not qa["technical_delivery_verified"] or not qa[
                    "full_picture_and_sound_decoder_completed"]:
                raise RuntimeError("Entire film picture/sound failed actual full decoding")
            if sha256_file(plan_file)!=before or any(
                    sha256_file(path)!=digest for path,digest in originals.items()):
                raise ValueError("Original footage or director cut changed while encoding")
            if any(sha256_file(path)!=digest for (digest,_),path in pinned.items()):
                raise ValueError("Sealed original footage changed while encoding")
            # Recheck CAS bytes and original rights on the committing side of
            # the native subprocess, not merely at the beginning of the edit.
            vault=MediaVault(vault_root)
            for clip in plan["clips"]:
                stored=vault.inspect(clip["asset_id"],
                        attestation_id=clip["attestation_id"])
                if stored["rights_attestations"][0]["rights"]!=clip["rights"]:
                    raise ValueError("Original source rights changed during encoding")
            with staged.open("rb") as verified_output:
                os.fsync(verified_output.fileno())
            # Only a single atomic, exclusive hardlink may expose a fully
            # decoded, still-rights-attested movie. A competitor wins safely.
            os.link(staged,output)
        return {"sha256":sha256_file(output),
                "source_attestations":canonical_source_attestations([
                    {k:clip[k] for k in ("asset_id","attestation_id")} for clip in plan["clips"]]),
                "source_custody_count":len(clean["clips"]),
                "distinct_originals":len(originals),
                "plan_sha256":before,
                "encoded_media_probe":final,
                "original_footage_unchanged":True,
                "sealed_original_cas_during_decode":True,
                "full_picture_and_sound_decoder_completed":True,
                "technical_delivery_verified":True,
                "ownership_independently_legally_certified":False,
                "artistic_quality_certified":False}
    except BaseException:
        # TemporaryDirectory cleans OUR private render on every failure.
        # Never unlink the public destination: another writer may own it.
        raise
