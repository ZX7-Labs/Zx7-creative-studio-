"""Portable physical creative-body snapshot and crash-safe workspace restore.

Persists the actual bytes of edited shots, media custody, original assets,
SQLite WAL-safe production checkpoints and chosen editor inputs. This is NOT
a creative template or "save chat" feature. The exact project root must be
restored before reusing old graph outputs with absolute output witnesses.

Operator-owned archive SHA256 is required for authenticity on restore; an
internal digest manifest alone is only corruption detection and is not a
cryptographic signature. No remote provider or subscription.
"""
from __future__ import annotations

from contextlib import closing
import ctypes
import errno
import hashlib
import io
import json
import os
import shutil
import sqlite3
import sys
import tarfile
import tempfile
from pathlib import Path

from .media_vault import sha256_file
from .body_portability import prepare_relocated_workspace

_MANIFEST="__zx7_body_snapshot_manifest__.json"
_MAGIC="ZX7-BODY-REAL-MEDIA-V1"


def _publish_restored_directory_exclusively(staged,target):
    """Publish a whole recovered project without replacing a racing owner.

    On supported Linux hosts renameat2(RENAME_NOREPLACE) is the only
    required atomic primitive. os.replace/os.rename can erase an existing
    empty approved workspace between preflight and commit. Do not silently
    claim cross-platform no-clobber behavior when this ABI is unavailable.
    """
    if sys.platform!="linux":
        raise RuntimeError("Exclusive atomic workspace restoration requires Linux renameat2")
    native=ctypes.CDLL(None,use_errno=True)
    rename=getattr(native,"renameat2",None)
    if rename is None:
        raise RuntimeError("Host lacks Linux atomic no-replace directory publication")
    rename.argtypes=[
        ctypes.c_int,ctypes.c_char_p,ctypes.c_int,
        ctypes.c_char_p,ctypes.c_uint]
    rename.restype=ctypes.c_int
    if rename(-100,os.fsencode(staged),-100,os.fsencode(target),1)!=0:
        error=ctypes.get_errno()
        if error==errno.EEXIST:
            raise FileExistsError(
                errno.EEXIST,"Another operator already published this workspace",
                str(target))
        raise OSError(error,os.strerror(error),str(target))


# Private staging directories never become supposedly approved project media.
_PRIVATE_RENDER_PREFIXES=(
    ".zx7-owned-sources-",
    ".zx7-media-review-",
    ".zx7-subtitle-",
    ".zx7-original-exr-render-",
    ".zx7-scene-seal-",
    ".zx7-temporal-",
    ".zx7-aces2-",
    ".zx7-aces2-movie-",
    ".zx7-review-frame-",
    ".zx7-comfy-stage-",
    ".zx7-relink-seal-",
    ".zx7-verified-relink-",
    ".zx7-import-",
    ".zx7-uncommitted-",
    ".zx7-otio-import-",
    ".zx7-nle-",
    ".zx7-incomplete-",
    ".zx7-vault-checkout-",
    ".zx7-composite-render-",
    ".zx7-plan-",
    ".zx7-stage-checkpoint-",
    ".comfy_prompt-",
)


def _name(path):
    if not isinstance(path,str) or not path or path.startswith("/") or (
            "\\" in path or any(p in ("","..",".") for p in path.split("/"))):
        raise ValueError("Untrusted archive path cannot leave film workspace")
    if path==_MANIFEST:
        raise ValueError("Original media cannot shadow production manifest")
    if any(component.startswith(_PRIVATE_RENDER_PREFIXES)
           for component in path.split("/")):
        raise ValueError("Transient sealed cinema sources cannot become project backups")
    return path


def _consistent_sqlite(original,target):
    """Back up live SQLite with its WAL, rather than copying stale DB bytes."""
    try:
        with closing(sqlite3.connect(Path(original).absolute().as_uri()+"?mode=ro",
                                     uri=True,timeout=20)) as reader:
            with closing(sqlite3.connect(target,timeout=20)) as writer, writer:
                reader.backup(writer,pages=256,sleep=.05)
                check=writer.execute("PRAGMA quick_check").fetchone()
                if check!=("ok",):
                    raise ValueError("Physical creative checkpoint database corrupted")
    except sqlite3.DatabaseError as exc:
        raise ValueError("Failed to create consistent original SQLite checkpoint") from exc


def create_body_archive(workspace,archive):
    """Make a self-contained snapshot without changing accepted film artifacts."""
    root=Path(workspace).resolve()
    out=Path(archive).resolve()
    if not root.is_dir() or out.is_relative_to(root):
        raise ValueError("Place snapshot outside an existing project directory")
    if out.exists() or out.parent==root:
        raise ValueError("No overwrite of actual prior project archive")
    out.parent.mkdir(parents=True,exist_ok=True)
    tmp=out.with_name("."+out.name+".uncommitted")
    if tmp.exists():
        raise FileExistsError("Incomplete previous physical archive requires inspection")
    with tempfile.TemporaryDirectory(prefix="zx7-sqlite-",dir=out.parent) as store:
        copies={}
        sources=[]
        for path in sorted(root.rglob("*")):
            if any(piece.startswith(_PRIVATE_RENDER_PREFIXES)
                   for piece in path.relative_to(root).parts):
                raise ValueError("Cannot archive private in-flight original media snapshots")
            if path.is_symlink():
                raise ValueError("Untrusted symlink in creative media workspace")
            if path.is_dir():
                continue
            if not path.is_file():
                raise ValueError("Nonregular creative source cannot be archived")
            relative=_name(path.relative_to(root).as_posix())
            if path.suffix in (".sqlite3-wal",".sqlite3-shm") or relative.endswith((
                    ".sqlite3-wal",".sqlite3-shm")):
                continue
            source=path
            if path.name.endswith(".sqlite3"):
                source=Path(store)/(str(len(copies))+".sqlite3")
                _consistent_sqlite(path,source)
                copies[relative]=str(source)
            sources.append((relative,source,path))
        rows=[]
        owned_stage=False
        try:
            with tarfile.open(tmp,"x:gz",format=tarfile.PAX_FORMAT) as tar:
                owned_stage=True
                for relative,source,original in sources:
                    before=sha256_file(source)
                    length=source.stat().st_size
                    item=tarfile.TarInfo(relative)
                    item.mode=0o600
                    item.size=length
                    item.mtime=0
                    with source.open("rb") as handle:
                        tar.addfile(item,handle)
                    if sha256_file(source)!=before or source.stat().st_size!=length:
                        raise RuntimeError("Creative media changed during snapshot")
                    if source==original and original.stat().st_size!=length:
                        raise RuntimeError("Original output modified while snapshotting")
                    rows.append({"path":relative,"sha256":before,"bytes":length})
                manifest={"kind":_MAGIC,"schema":1,
                          "source_workspace":str(root),"files":rows}
                payload=json.dumps(manifest,sort_keys=True,ensure_ascii=False,
                                   separators=(",",":")).encode("utf-8")
                info=tarfile.TarInfo(_MANIFEST)
                info.size=len(payload);info.mode=0o600;info.mtime=0
                tar.addfile(info,io.BytesIO(payload))
            digest=sha256_file(tmp)
            # Same-directory hardlink is a no-clobber atomic file publish.
            # Do NOT replace a racing artist's approved project backup.
            os.link(tmp,out)
        finally:
            # If a different backup process won exclusive stage creation,
            # this process has no right to erase that operator's archive.
            if owned_stage:
                tmp.unlink(missing_ok=True)
    return {"archive":str(out),"sha256":digest,"files":len(rows),
            "bytes":out.stat().st_size,"signed":False,
            "source_workspace":str(root),
            "claim":"Operator must retain archive digest in a trusted channel"}


def restore_body_archive(archive,destination,*,expected_sha256,relocate=False):
    """Validate *every* tar byte/path before publishing a restored workspace."""
    if type(relocate) is not bool:
        raise ValueError("Explicit boolean portable recovery permission required")
    source=Path(archive).resolve()
    target=Path(destination).resolve()
    if not isinstance(expected_sha256,str) or len(expected_sha256)!=64 or (
            sha256_file(source)!=expected_sha256):
        raise ValueError("Untrusted/corrupted physical production archive SHA256")
    if target.exists():
        raise FileExistsError("Restore only into an empty nonexisting workspace")
    target.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".zx7-restore-",dir=target.parent) as staging:
        temp=Path(staging)/"original"
        temp.mkdir()
        with tarfile.open(source,"r:gz") as tar:
            members=tar.getmembers()
            if not members or len(members)>200000:
                raise ValueError("Unbounded or empty creative backup directory")
            by_name={}
            for item in members:
                if not item.isfile() or item.issym() or item.islnk():
                    raise ValueError("No symlink, directory traversal or special archive members")
                if item.name in by_name:
                    raise ValueError("Duplicate original film archive entry")
                if item.name!=_MANIFEST:
                    _name(item.name)
                by_name[item.name]=item
            if _MANIFEST not in by_name:
                raise ValueError("Missing physical checkpoint digest index")
            manifest=json.load(tar.extractfile(by_name[_MANIFEST]))
            if not isinstance(manifest,dict) or manifest.get("kind")!=_MAGIC or (
                    manifest.get("schema")!=1):
                raise ValueError("Unknown film body archive schema")
            indexed=manifest.get("files")
            if not isinstance(indexed,list) or set(by_name)!={
                    _MANIFEST,*[x["path"] for x in indexed if isinstance(x,dict) and
                                 isinstance(x.get("path"),str)]}:
                raise ValueError("Manifest does not match original media archive")
            accounted=set()
            for row in indexed:
                if not isinstance(row,dict) or set(row)!={"path","sha256","bytes"}:
                    raise ValueError("Malformed actual film media record")
                rel=_name(row["path"])
                if rel in accounted or not isinstance(row["bytes"],int) or row["bytes"]<0:
                    raise ValueError("Duplicate or invalid media record")
                accounted.add(rel)
                if not isinstance(row["sha256"],str) or len(row["sha256"])!=64:
                    raise ValueError("Corrupted media digest manifest")
                member=by_name[rel]
                if member.size!=row["bytes"]:
                    raise ValueError("Physical media differs from stored size")
                output=temp/rel
                output.parent.mkdir(parents=True,exist_ok=True)
                sha=hashlib.sha256()
                with tar.extractfile(member) as readable, output.open("xb") as writable:
                    while True:
                        block=readable.read(1024*1024)
                        if not block:break
                        sha.update(block);writable.write(block)
                    writable.flush();os.fsync(writable.fileno())
                if sha.hexdigest()!=row["sha256"]:
                    raise ValueError("Restored movie/media bytes differ from immutable snapshot")
            for db in temp.rglob("*.sqlite3"):
                with closing(sqlite3.connect(db.absolute().as_uri()+"?mode=ro",uri=True)) as conn:
                    if conn.execute("PRAGMA quick_check").fetchone()!=("ok",):
                        raise ValueError("Restored scene checkpoint SQLite is corrupted")
            # Atomic publish into the same location used by original source
            # references. Reuse across changed paths requires explicit rebind.
            original_root=manifest.get("source_workspace")
            moved=None
            if original_root!=str(target):
                if not relocate:
                    raise ValueError("Restore path differs from original media references")
                moved=prepare_relocated_workspace(temp,old_root=original_root,
                    destination=target,archive_sha256=expected_sha256)
            elif relocate:
                raise ValueError("Cross-host migration requested at unchanged workspace path")
            # Namespace and SQLite metadata transformed only inside the
            # fully verified staging directory, before one atomic publication.
            _publish_restored_directory_exclusively(temp,target)
        return {"restored":str(target),"files":len(accounted),
                "archive_sha256":expected_sha256,"all_physical_bytes_verified":True,
                "artistic_project_preserved":True,
                "relocated":moved is not None,
                "old_execution_state_quarantined":moved is not None,
                "old_jobs_auto_resumable":moved is None}




def save_body_archive_offline(workspace,archive):
    """Quiescent operator CLI backup, refusing a live render service or job.

    The in-process coordinator has its own maintenance lease; standalone
    operators acquire the same cross-process host lock before reading files.
    """
    import fcntl
    root=Path(workspace).resolve()
    if not root.is_dir():
        raise ValueError("Original workspace must exist for offline snapshot")
    gate=root/"body-service.lock"
    if gate.is_symlink():
        raise ValueError("Untrusted production service lock link")
    with gate.open("a+") as handle:
        try:
            fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Production service running; use its maintenance snapshot API") from exc
        try:
            database=root/"body-jobs.sqlite3"
            if database.exists():
                with closing(sqlite3.connect(database.absolute().as_uri()+"?mode=ro",uri=True)) as conn:
                    active=conn.execute(
                        "SELECT COUNT(*) FROM jobs WHERE status IN ('queued','running')"
                    ).fetchone()[0]
                if active:
                    raise RuntimeError("Cannot snapshot unresolved active original media jobs")
            if next(root.rglob(".zx7-import-*.tmp"),None) is not None:
                raise RuntimeError("Original owner media transfer is incomplete")
            return create_body_archive(root,archive)
        finally:
            fcntl.flock(handle.fileno(),fcntl.LOCK_UN)


def main(argv=None):
    """Host-operator-only archive tool. No executable model instructions."""
    import argparse
    p=argparse.ArgumentParser(description="Verified original ZX7 BODY archival and safe cross-host recovery")
    actions=p.add_subparsers(dest="command",required=True)
    save=actions.add_parser("save",help="Create SHA-256-verified original work archive")
    save.add_argument("--workspace",type=Path,required=True)
    save.add_argument("--archive",type=Path,required=True)
    restore=actions.add_parser("restore",help="Restore trusted archive to an empty workspace")
    restore.add_argument("--archive",type=Path,required=True)
    restore.add_argument("--destination",type=Path,required=True)
    restore.add_argument("--sha256",required=True,help="Original 64-digit SHA256 from trusted offline channel")
    restore.add_argument("--relocate",action="store_true",
        help="Import to a DIFFERENT host path, quarantine old executable jobs and require safe relinking")
    args=p.parse_args(argv)
    if args.command=="save":
        result=save_body_archive_offline(args.workspace,args.archive)
    else:
        result=restore_body_archive(args.archive,args.destination,
             expected_sha256=args.sha256,relocate=args.relocate)
    print(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2))
    return result


if __name__=="__main__":
    main()
