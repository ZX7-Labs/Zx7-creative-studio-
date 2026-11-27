"""Durable rights-checked content-addressed asset vault for all creative media.

The model can request an image, sound, font, mesh, footage, thumbnail or film,
but cannot turn an arbitrary internet URL, imagined asset or unlicensed material
into studio media. The bytes, provenance and usage authorization are separately
tracked. This is technical custody, not a creative style or story prompt.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import tempfile
import time
from pathlib import Path
from .durable_sqlite import connect_durable_database

_DIGEST=re.compile(r"^[0-9a-f]{64}$")
_RIGHTS={"owner_supplied","generated_original","appropriately_licensed"}
_ALLOWED_MIME={"image/png","image/jpeg","image/webp","image/svg+xml",
 "image/x-exr","video/mp4","video/quicktime","video/webm",
 "audio/wav","audio/mpeg","audio/flac","font/ttf","font/otf",
 "model/gltf-binary","application/octet-stream",
 "application/x-zx7-exr-bundle"}
class MediaCustodyError(ValueError):
    pass


def verify_media_container(path,mime):
    """Physical decoder/magic check; provenance text alone cannot create a film."""
    path=Path(path)
    if mime.startswith("video/"):
        if shutil.which("ffprobe") is None:
            raise MediaCustodyError("Real video decoder not installed; refuse unverifiable source")
        from .delivery_audit import _probe_details
        from .edit_timeline import SELF_CONTAINED_VIDEO_INPUT
        import subprocess
        try:
            observed=_probe_details(path)
            decoded=subprocess.run([
                "ffmpeg","-hide_banner","-loglevel","error","-nostdin",
                "-xerror",*SELF_CONTAINED_VIDEO_INPUT,"-i",str(path),"-map","0:v",
                "-map","0:a?","-f","null","-"],
                capture_output=True,timeout=3600,check=False)
            if decoded.returncode!=0:
                raise MediaCustodyError(
                    "Original video failed complete physical picture/audio decode")
            return observed
        except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as exc:
            # Source footage failures are an ordinary untrusted upload error,
            # not an uncaught internal server exception or valid asset.
            raise MediaCustodyError("Claimed video has no real decodable media stream") from exc
    if mime=="image/png":
        with path.open("rb") as f:
            first=f.read(24)
        if len(first)<24 or first[:8]!=bytes([137,80,78,71,13,10,26,10]) or (
             int.from_bytes(first[16:20],"big")<=0 or
             int.from_bytes(first[20:24],"big")<=0):
            raise MediaCustodyError("Original PNG image signature and dimensions are invalid")
        try:
            from PIL import Image
        except ImportError:
            # Do not mistake a leading PNG signature for real image pixels.
            # Production hosts with image tools have either Pillow or FFmpeg.
            if shutil.which("ffmpeg") is None:
                raise MediaCustodyError("A real PNG decoder is not installed")
            import subprocess
            decoded=subprocess.run(["ffmpeg","-hide_banner","-loglevel","error",
                      "-xerror","-nostdin","-i",str(path),
                      "-frames:v","1","-f","null","-"],
                      capture_output=True,timeout=90,check=False)
            if decoded.returncode!=0:
                raise MediaCustodyError("Claimed original PNG is not pixel-decodable")
        else:
            try:
                with Image.open(path) as image:
                    image.verify()
                with Image.open(path) as image:
                    image.load()
                    if image.width<=0 or image.height<=0:
                        raise MediaCustodyError("Empty original PNG image")
            except (OSError,ValueError,SyntaxError) as exc:
                raise MediaCustodyError("Claimed original PNG is not pixel-decodable") from exc
    elif mime=="audio/wav":
        from .pcm_wave import inspect_pcm_wav
        import subprocess
        try:
            # Integer PCM carries samples as fixed-width bytes, not an encoded
            # bitstream. Complete RIFF chunk extents, exact block alignment,
            # channel layout and sample clock can be independently verified
            # without a separate multimedia executable. Do not deny valid
            # owner audio on an otherwise minimal Python-only host.
            inspect_pcm_wav(path)
        except ValueError as exc:
            raise MediaCustodyError(str(exc)) from exc
        # When a physical FFmpeg decoder is actually installed, perform an
        # additional full decoder cross-check. Its absence is not proof that
        # fixed-width integer PCM samples are undecodable. Compressed WAV
        # codecs are never admitted by inspect_pcm_wav.
        if shutil.which("ffmpeg") is not None:
            try:
                decoded=subprocess.run([
                    "ffmpeg","-hide_banner","-loglevel","error","-nostdin",
                    "-xerror","-i",str(path),"-map","0:a","-f","null","-"],
                    capture_output=True,timeout=3600,check=False)
                if decoded.returncode:
                    raise MediaCustodyError("Original PCM WAV failed full audio decode")
            except MediaCustodyError:
                raise
            except (OSError,subprocess.SubprocessError) as exc:
                raise MediaCustodyError("Original PCM WAV cannot be fully decoded") from exc
    elif mime=="image/svg+xml":
        from .creative_asset_ops import validate_original_svg_art
        validate_original_svg_art(path)
    elif mime in ("font/ttf","font/otf"):
        # Source owners can attest a font license only after actual sfnt glyph
        # metadata parses. A four-byte sfnt signature or fabricated name
        # table is not proof of an artist-usable text shaping resource.
        import importlib.util
        if importlib.util.find_spec("fontTools") is None:
            raise MediaCustodyError("Native font source decoder not installed")
        from fontTools.ttLib import TTFont,TTLibError
        import struct
        with path.open("rb") as actual_font:
            signature=actual_font.read(4)
        if ((mime=="font/ttf" and signature not in (
                    bytes((0,1,0,0)),b"true"))
                or (mime=="font/otf" and signature!=b"OTTO")):
            raise MediaCustodyError("Original font sfnt container does not match MIME")
        try:
            with TTFont(str(path),lazy=False,recalcBBoxes=False) as face:
                cmap=face.getBestCmap()
                if (not isinstance(cmap,dict) or not cmap
                        or not 1<=face["maxp"].numGlyphs<=200000
                        or not 16<=face["head"].unitsPerEm<=16384):
                    raise MediaCustodyError(
                        "Original typeface has no real Unicode glyph metrics")
        except (OSError,ValueError,KeyError,TTLibError,AssertionError,
                IndexError,TypeError,struct.error) as exc:
            raise MediaCustodyError(
                "Original claimed typeface failed native font table/glyph inspection") from exc
    elif mime=="model/gltf-binary":
        # glTF v2 GLB is a precisely chunked binary container, not twelve
        # bytes beginning with "glTF". Verify actual JSON scene metadata and
        # every chunk boundary before granting source rights. This verifies
        # binary structure, NOT artistic geometry, UVs, shader or render quality.
        import struct
        size=path.stat().st_size
        if size<32 or size>2*1024*1024*1024:
            raise MediaCustodyError("Original GLB has no bounded complete scene")
        try:
            with path.open("rb") as scene:
                magic,version,declared=struct.unpack("<4sII",scene.read(12))
                if magic!=b"glTF" or version!=2 or declared!=size:
                    raise MediaCustodyError("Original GLB header/version/size is false")
                visited=12
                first_json=None
                chunks=0
                has_binary=False
                binary_chunk_bytes=None
                while visited<size:
                    header=scene.read(8)
                    if len(header)!=8:
                        raise MediaCustodyError("Truncated original GLB chunk header")
                    length,kind=struct.unpack("<I4s",header)
                    visited+=8
                    if length%4!=0 or length>size-visited or chunks>=64:
                        raise MediaCustodyError("Invalid native GLB chunk boundary")
                    if chunks==0:
                        if kind!=b"JSON" or not 4<=length<=8*1024*1024:
                            raise MediaCustodyError("GLB has no bounded native JSON scene")
                        first_json=json.loads(scene.read(length).rstrip(bytes((32,9,13,10,0))))
                        if not isinstance(first_json,dict):
                            raise MediaCustodyError("GLB scene description is not JSON")
                    else:
                        if kind==b"JSON" or (kind==bytes((66,73,78,0)) and has_binary):
                            raise MediaCustodyError("GLB has duplicate scene or binary chunks")
                        if kind==bytes((66,73,78,0)):
                            has_binary=True
                            binary_chunk_bytes=length
                        scene.seek(length,1)
                    visited+=length
                    chunks+=1
                if visited!=size:
                    raise MediaCustodyError("Native GLB file contains undeclared bytes")
                if (not isinstance(first_json,dict)
                        or first_json.get("asset",{}).get("version")!="2.0"
                        or not isinstance(first_json.get("scenes"),list)
                        or not first_json["scenes"]
                        or not isinstance(first_json.get("nodes"),list)
                        or not first_json["nodes"]
                        or not (first_json.get("meshes") or first_json.get("cameras"))):
                    raise MediaCustodyError(
                        "Original GLB lacks a real scene graph and authored geometry/camera")
                buffers=first_json.get("buffers",[])
                if not isinstance(buffers,list):
                    raise MediaCustodyError("Original GLB has malformed buffer references")
                if buffers:
                    if len(buffers)!=1 or not has_binary:
                        raise MediaCustodyError("GLB describes missing required binary source")
                    buffer=buffers[0]
                    if (not isinstance(buffer,dict) or
                            type(buffer.get("byteLength")) is not int or
                            buffer["byteLength"]<1 or
                            "uri" in buffer or
                            not buffer["byteLength"]<=binary_chunk_bytes<=
                                 buffer["byteLength"]+3):
                        raise MediaCustodyError(
                            "Original GLB binary payload differs from its scene graph")
                    for view in first_json.get("bufferViews",[]):
                        if (not isinstance(view,dict)
                                or view.get("buffer")!=0
                                or type(view.get("byteLength")) is not int
                                or type(view.get("byteOffset",0)) is not int
                                or view["byteLength"]<1
                                or view.get("byteOffset",0)<0
                                or view.get("byteOffset",0)+view["byteLength"]>
                                   buffer["byteLength"]):
                            raise MediaCustodyError(
                                "Original GLB geometry buffer view escapes physical bytes")
                elif has_binary:
                    raise MediaCustodyError(
                        "Unreferenced or fake binary 3D payload in original GLB")
                if first_json.get("meshes") and not buffers:
                    raise MediaCustodyError(
                        "Original GLB mesh has no complete geometry buffer")
        except (OSError,struct.error,UnicodeDecodeError,
                json.JSONDecodeError,TypeError,AttributeError) as exc:
            raise MediaCustodyError("Original GLB failed full binary scene verification") from exc
    elif mime=="image/x-exr":
        # Standalone, potentially owner-supplied scene-linear EXR must be
        # physically decoded. A matching EXR magic prefix, filename or
        # rights string is never evidence of usable pixels.
        import importlib.util
        if importlib.util.find_spec("OpenEXR") is None:
            raise MediaCustodyError("Original OpenEXR decoder is not installed")
        import OpenEXR
        try:
            with path.open("rb") as data:
                if data.read(4)!=bytes((0x76,0x2f,0x31,0x01)):
                    raise MediaCustodyError("Original image has no real OpenEXR magic")
            with OpenEXR.File(str(path),separate_channels=True) as exr:
                if not exr.parts:
                    raise MediaCustodyError("Original EXR has no decoded native image part")
                usable=False
                for part in exr.parts:
                    width,height=part.width(),part.height()
                    if (not isinstance(width,int) or not isinstance(height,int)
                            or not 1<=width<=32768 or not 1<=height<=32768
                            or width*height>120000000):
                        raise MediaCustodyError("Original EXR image dimensions are not bounded")
                    if not part.channels:
                        raise MediaCustodyError("Original EXR image has no physical channels")
                    for channel in part.channels.values():
                        pixels=channel.pixels
                        if (pixels is None or pixels.shape[0]!=height
                                or pixels.shape[1]!=width or
                                str(pixels.dtype) not in ("float16","float32","uint32")):
                            raise MediaCustodyError(
                                "Original EXR channel has no decoded pixel plane")
                        usable=True
                if not usable:
                    raise MediaCustodyError("Original EXR contains no actual pixels")
        except (OSError,RuntimeError,ValueError,TypeError,IndexError) as exc:
            raise MediaCustodyError(
                "No fully decoded native OpenEXR original image") from exc
    elif mime=="application/x-zx7-exr-bundle":
        # Never grant trusted CG source rights to an arbitrary ZIP or opaque
        # binary. Real native OpenEXR re-decodes ALL physically rendered
        # float32 RGBA, depth, normal and motion passes on ingest.
        from .body_exr_passes import verify_exr_bundle
        import zipfile
        try:
            actual=verify_exr_bundle(path)
            if not (actual["original_exr_passes_real"] and
                    actual["reloaded_every_frame_and_sha256_verified"]):
                raise MediaCustodyError("Unverified original 32f EXR frame archive")
        except (ValueError,RuntimeError,TypeError,OSError,KeyError,
                zipfile.BadZipFile) as exc:
            raise MediaCustodyError(
                "Not a physically decoded and verified native 32f EXR bundle") from exc
    elif mime in ("audio/mpeg","audio/flac"):
        import subprocess
        # Do not let a reference-only playlist confer custody of its targets.
        audio_input=("-protocol_whitelist","file,pipe","-format_whitelist",
                     "mp3" if mime=="audio/mpeg" else "flac")
        try:
            data=json.loads(subprocess.check_output(["ffprobe","-v","error",*audio_input,
                  "-show_entries","stream=codec_type","-of","json",str(path)],timeout=60))
        except (OSError,ValueError,subprocess.SubprocessError) as exc:
            raise MediaCustodyError("Claimed audio does not contain a decodable stream") from exc
        if not any(x.get("codec_type")=="audio" for x in data.get("streams",[])):
            raise MediaCustodyError("No original decoded source sound")
        decoded=subprocess.run([
            "ffmpeg","-hide_banner","-loglevel","error","-nostdin",
            "-xerror",*audio_input,"-i",str(path),"-map","0:a:0",
            "-f","null","-"],capture_output=True,timeout=3600,check=False)
        if decoded.returncode!=0:
            raise MediaCustodyError("Original compressed sound failed full decoder")
    elif mime.startswith("image/"):
        try:
            from PIL import Image
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                image.load()
                if image.width<1 or image.height<1:
                    raise MediaCustodyError("Original graphic contains no actual pixels")
        except (ImportError,OSError,ValueError) as exc:
            raise MediaCustodyError("No decoded original graphic available") from exc
    # font/ttf, font/otf and binary originals require trusted import provenance
    # and specialized renderers inspect them before use; never call them video.
    return {"actual_file_bytes_checked":True}


def sha256_file(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle,"sha256").hexdigest()


class MediaVault:
    """SQLite WAL + atomic immutable blobs; empty results are never delivered."""
    def __init__(self,root,*,initialize=True):
        if type(initialize) is not bool:
            raise MediaCustodyError("Vault initialization policy must be an explicit boolean")
        supplied=Path(root)
        if supplied.is_symlink():
            raise MediaCustodyError("Source vault root cannot be a linked external directory")
        self.root=supplied.resolve()
        self.objects=self.root/"objects"
        self.db=self.root/"assets.sqlite3"
        if self.objects.is_symlink() or self.db.is_symlink():
            raise MediaCustodyError("Source vault cannot use an external linked object or database")
        if not initialize:
            return  # Pure native tool discovery: no SQLite, directories, or asset writes.
        self.objects.mkdir(parents=True,exist_ok=True)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS blobs(
              digest TEXT PRIMARY KEY, size_bytes INTEGER NOT NULL,
              mime TEXT NOT NULL, created_at REAL NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS attestations(
              digest TEXT NOT NULL, attestation_id TEXT NOT NULL,
              rights TEXT NOT NULL, source_type TEXT NOT NULL,
              source_id TEXT NOT NULL, evidence TEXT NOT NULL,
              owner_or_generator TEXT NOT NULL, created_at REAL NOT NULL,
              PRIMARY KEY(digest,attestation_id),
              FOREIGN KEY(digest) REFERENCES blobs(digest))""")
            db.execute("CREATE INDEX IF NOT EXISTS attested_digest ON attestations(digest)")

    def _connect(self):
        if self.db.is_symlink():
            raise MediaCustodyError("Original source custody DB was replaced by a link")
        db=connect_durable_database(self.db)
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def _loc(self,digest):
        if not isinstance(digest,str) or not _DIGEST.fullmatch(digest):
            raise MediaCustodyError("Unsafe media content digest")
        parent=self.objects/digest[:2]
        if self.objects.is_symlink() or parent.is_symlink():
            raise MediaCustodyError("Media address escapes original content vault by symlink")
        return parent/digest

    def ingest(self,source,*,mime,rights,source_type,source_id,evidence,
               owner_or_generator):
        """Attest real file source and rights; never infer rights from an extension."""
        if mime not in _ALLOWED_MIME or rights not in _RIGHTS:
            raise MediaCustodyError("Unsupported media type or unverified rights class")
        for value in (source_type,source_id,evidence,owner_or_generator):
            if not isinstance(value,str) or not value.strip():
                raise MediaCustodyError("Explicit original source and media rights evidence required")
        if source_type not in ("owner_upload","trusted_renderer","licensed_library"):
            raise MediaCustodyError("No authenticated source class for media")
        expected={"owner_upload":"owner_supplied",
                  "trusted_renderer":"generated_original",
                  "licensed_library":"appropriately_licensed"}[source_type]
        if rights!=expected:
            raise MediaCustodyError("Declared rights disagree with original media source")
        path=Path(source)
        if not path.is_file() or path.stat().st_size==0:
            raise MediaCustodyError("Asset has no actual file bytes")
        if self.objects.is_symlink():
            raise MediaCustodyError("Source vault cannot use an external linked object directory")
        # Validate the private staged snapshot, never a mutable upload path
        # that can be replaced between physical decoding and CAS publication.
        fd,tmp=tempfile.mkstemp(prefix=".ingest-",dir=self.objects)
        try:
            with os.fdopen(fd,"wb") as handle, path.open("rb") as stream:
                before=os.fstat(stream.fileno())
                shutil.copyfileobj(stream,handle,1024*1024)
                handle.flush();os.fsync(handle.fileno())
                after=os.fstat(stream.fileno())
            size=Path(tmp).stat().st_size
            if not size or size!=before.st_size or (
                    before.st_size,before.st_mtime_ns,before.st_ctime_ns)!= (
                    after.st_size,after.st_mtime_ns,after.st_ctime_ns):
                raise MediaCustodyError("Source changed while ingesting")
            digest=sha256_file(tmp)
            verify_media_container(tmp,mime)
            if sha256_file(tmp)!=digest:
                raise MediaCustodyError("Staged media changed during physical verification")
            dest=self._loc(digest)
            dest.parent.mkdir(parents=True,exist_ok=True)
            if dest.is_symlink():
                raise MediaCustodyError("Content-addressed creative media may not be a symlink")
            if not dest.is_file():
                try:
                    os.link(tmp,dest)
                except FileExistsError:
                    # Two independent producers can race to publish IDENTICAL
                    # CAS bytes; an unrelated winner is not trusted.
                    if dest.is_symlink() or not dest.is_file() or sha256_file(dest)!=digest:
                        raise MediaCustodyError(
                            "Another publisher placed different bytes in immutable MediaVault")
            elif sha256_file(dest)!=digest:
                raise MediaCustodyError("Previously saved media content is corrupted")
            if dest.stat().st_size!=size:
                raise MediaCustodyError("Mismatch in bytes of durable creative media")
        finally:
            Path(tmp).unlink(missing_ok=True)
        attestation={
            "rights":rights,"source_type":source_type,"source_id":source_id,
            "evidence":evidence,"owner_or_generator":owner_or_generator,
            "digest":digest}
        encoded=json.dumps(attestation,sort_keys=True,ensure_ascii=False).encode()
        att_id=hashlib.sha256(encoded).hexdigest()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            old=db.execute("SELECT size_bytes,mime FROM blobs WHERE digest=?",(digest,)).fetchone()
            if old is not None and tuple(old)!=(size,mime):
                db.execute("ROLLBACK")
                raise MediaCustodyError("Contradictory MIME or file size for same content")
            db.execute("INSERT OR IGNORE INTO blobs VALUES(?,?,?,?)",
                       (digest,size,mime,time.time()))
            db.execute("INSERT OR IGNORE INTO attestations VALUES(?,?,?,?,?,?,?,?)",
                 (digest,att_id,rights,source_type,source_id,evidence,owner_or_generator,time.time()))
            db.execute("COMMIT")
        return {"asset_id":digest,"attestation_id":att_id,"mime":mime,
                "rights":rights,"size_bytes":size,"verified_bytes":True}

    def inspect(self,digest,*,attestation_id=None):
        path=self._loc(digest)
        with self._connect() as db:
            blob=db.execute("SELECT size_bytes,mime FROM blobs WHERE digest=?",(digest,)).fetchone()
            if blob is None:raise MediaCustodyError("Unknown media reference")
            if attestation_id is None:
                rows=db.execute("SELECT attestation_id,rights,source_type,source_id,evidence,owner_or_generator FROM attestations WHERE digest=?",
                              (digest,)).fetchall()
            else:
                rows=db.execute("SELECT attestation_id,rights,source_type,source_id,evidence,owner_or_generator FROM attestations WHERE digest=? AND attestation_id=?",
                               (digest,attestation_id)).fetchall()
        if not rows or path.is_symlink() or not path.is_file() or path.stat().st_size!=blob[0] or sha256_file(path)!=digest:
            raise MediaCustodyError("Missing or altered stored media and provenance")
        return {"asset_id":digest,"size_bytes":blob[0],"mime":blob[1],
                "path":str(path),"rights_attestations":[{
                    "attestation_id":a,"rights":b,"source_type":c,
                    "source_id":d,"evidence":e,"owner_or_generator":f}
                    for a,b,c,d,e,f in rows]}

    def checkout(self,digest,attestation_id,destination):
        """Restore verified bytes into a working scene and keep original immutable."""
        record=self.inspect(digest,attestation_id=attestation_id)
        dest=Path(destination)
        if dest.exists():raise MediaCustodyError("Never overwrite earlier creative work")
        dest.parent.mkdir(parents=True,exist_ok=True)
        fd,stage=tempfile.mkstemp(prefix=".zx7-vault-checkout-",
                                  dir=dest.parent)
        try:
            with os.fdopen(fd,"wb") as out,Path(record["path"]).open("rb") as src:
                shutil.copyfileobj(src,out,1024*1024)
                out.flush()
                os.fsync(out.fileno())
            if sha256_file(stage)!=digest:
                raise MediaCustodyError(
                    "Copied creative media differs from immutable source")
            self.inspect(digest,attestation_id=attestation_id)
            os.link(stage,dest)
        finally:
            Path(stage).unlink(missing_ok=True)
        return record
