"""Native Blender project transactions, runtime RNA discovery and media delivery.

The host installs Blender; the artist authors project data. Every transaction
opens a sealed project in a fresh process, edits native data, renders requested
frames and publishes a new self-contained version. No style compiler is used.
"""
from __future__ import annotations
import hashlib
from functools import lru_cache
import json
import math
import os
from fractions import Fraction
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

VERSION = "zx7-native-motion/1"
METHODS = ("new", "remove", "clear", "link", "unlink", "add", "insert", "append",
           "new_socket", "from_pydata", "update", "foreach_set", "keyframe_insert", "keyframe_delete")


@lru_cache(maxsize=8)
def _engine_version(binary,mtime,size):
    import re
    output=subprocess.check_output([binary,"--version"],text=True,timeout=15)
    match=re.search(r"Blender (\d+)\.(\d+)",output)
    return tuple(map(int,match.groups())) if match else (0,0)


def motion_runtime_ready():
    binary=shutil.which("blender")
    if not binary:return False
    try:
        stat=Path(binary).stat()
        return _engine_version(binary,stat.st_mtime_ns,stat.st_size)>=(4,5)
    except (OSError,subprocess.SubprocessError):return False


def motion_document_schema():
    def obj(properties):return {"type":"object","required":list(properties),"properties":properties,"additionalProperties":False}
    text={"type":"string","minLength":1};integer={"type":"integer"}
    path={"type":"array","minItems":1,"maxItems":64,"items":{"oneOf":[text,integer]}}
    actions=[]
    for op,extra in (("set",{"value":{}}),("call",{"method":{"enum":list(METHODS)},
        "args":{"type":"array","items":{}},"kwargs":{"type":"object","required":[],"properties":{},"additionalProperties":True},
        "as":{"oneOf":[text,{"type":"null"}]}}),("read",{}),("describe",{}),
        ("list",{"offset":{"type":"integer","minimum":0},"limit":{"type":"integer","minimum":1,"maximum":256}})):
        actions.append(obj({"op":{"enum":[op]},"path":path,**extra}))
    vector={"type":"array","minItems":3,"maxItems":3,"items":{"type":"number","minimum":-1000000,"maximum":1000000}}
    bone=obj({"name":{"type":"string","minLength":1,"maxLength":63},"head":vector,"tail":vector,
        "roll":{"type":"number","minimum":-2*math.pi,"maximum":2*math.pi},
        "parent":{"oneOf":[text,{"type":"null"}]},"connected":{"type":"boolean"}})
    actions.append(obj({"op":{"enum":["define_armature_bones"]},"path":path,
        "bones":{"type":"array","minItems":1,"maxItems":1024,"items":bone}}))
    schema=obj({"version":{"enum":[VERSION]},"project":{"oneOf":[text,{"type":"null"}]},
        "actions":{"type":"array","items":{"oneOf":actions},"maxItems":10000},
        "renders":{"type":"array","maxItems":10000,"items":obj({"scene":text,"frame":integer,"format":{"enum":["png","exr32"]}})}})
    schema["description"]=("Native Blender 4.5+ project transaction. Root paths: data -> bpy.data, scene -> active scene, refs -> named call returns. "
        "Path tokens select public native RNA attributes, named collection members or integer indices. set edits RNA properties/array elements; "
        "call invokes native data construction/animation methods. args/kwargs may contain literal JSON values, arrays or {$ref:path} pointer values. "
        "define_armature_bones creates an explicitly authored bone hierarchy on an empty, local armature object in the active view layer; rest coordinates are armature-local. "
        "Use native vertex groups, modifiers and pose keyframes for skin and motion. "
        "describe returns installed RNA properties/enums and available data methods; list pages native collections; read observes a property. "
        "All actions form one isolated transaction and publish a new native project; project null starts empty. renders use authored scene names "
        "and original frame numbers in delivery order. Engine/render settings belong to the artist. Paths, script execution and dependencies are host-managed. "
        "Only self-contained packed projects currently accepted; no arbitrary operator/Python execution or unsealed external cache import.")
    return schema


def validate_armature_bones(bones):
    """Admit bounded native rest topology without guessing weights or joints."""
    if not isinstance(bones,list) or not 1<=len(bones)<=1024:
        raise ValueError("Armature requires 1..1024 explicitly authored bones")
    by_name={}
    for bone in bones:
        if not isinstance(bone,dict) or set(bone)!={"name","head","tail","roll","parent","connected"}:
            raise ValueError("Invalid native bone fields")
        name=bone["name"]
        if (not isinstance(name,str) or not name.strip() or len(name.encode("utf-8"))>63 or
            any(ord(c)<32 or ord(c)==127 for c in name) or name in by_name):
            raise ValueError("Bone names must be unique native names of at most 63 UTF-8 bytes")
        for point in (bone["head"],bone["tail"]):
            if (not isinstance(point,list) or len(point)!=3 or any(type(x) not in (int,float) or
                not -1000000<=x<=1000000 for x in point)):
                raise ValueError("Rest coordinates must be bounded finite armature-local vectors")
        if sum((a-b)**2 for a,b in zip(bone["head"],bone["tail"]))<1e-10:
            raise ValueError("Bone must have nonzero rest length")
        if type(bone["roll"]) not in (int,float) or not -2*math.pi<=bone["roll"]<=2*math.pi:
            raise ValueError("Bone roll must be finite radians in [-2pi,2pi]")
        if (bone["parent"] is not None and not isinstance(bone["parent"],str)) or type(bone["connected"]) is not bool:
            raise ValueError("Invalid native parent or connection flag")
        by_name[name]=bone
    for bone in bones:
        parent=bone["parent"]
        if parent is not None and parent not in by_name:
            raise ValueError("Unknown bone parent")
        if bone["connected"] and (parent is None or bone["head"]!=by_name[parent]["tail"]):
            raise ValueError("Connected child head must exactly meet parent tail")
    for bone in bones:
        parent=bone["parent"];seen={bone["name"]}
        while parent is not None:
            if parent in seen:raise ValueError("Cyclic native bone hierarchy")
            seen.add(parent);parent=by_name[parent]["parent"]
    return bones


def validate_motion_job(job):
    if not isinstance(job,dict) or set(job)!={"version","project","actions","renders"} or job["version"]!=VERSION:
        raise ValueError("Native motion job requires version/project/actions/renders")
    if job["project"] is not None and (not isinstance(job["project"],str) or not job["project"].endswith(".zxmotion")):
        raise ValueError("Project must be null or a sealed native .zxmotion version")
    if not isinstance(job["actions"],list) or len(job["actions"])>10000:
        raise ValueError("Native action budget exceeded")
    def path(p):
        if (not isinstance(p,list) or not 1<=len(p)<=64 or p[0] not in ("data","scene","refs")
            or any(type(x) not in (str,int) or isinstance(x,str) and (not x or x.startswith("_")) for x in p)):
            raise ValueError("Invalid native RNA reference")
    def values(v,depth=0):
        if depth>64:raise ValueError("Native argument nesting exceeds budget")
        if isinstance(v,dict):
            if set(v)!={"$ref"}:raise ValueError("Only a native $ref object is an argument value")
            path(v["$ref"])
        elif isinstance(v,list):
            for item in v:values(item,depth+1)
        elif v is not None and type(v) not in (str,int,float,bool):raise ValueError("Unsupported native argument")
    for action in job["actions"]:
        if not isinstance(action,dict):raise ValueError("Native actions must be objects")
        op=action.get("op")
        fields={"set":{"op","path","value"},"call":{"op","path","method","args","kwargs","as"},
                "read":{"op","path"},"describe":{"op","path"},"list":{"op","path","offset","limit"},
                "define_armature_bones":{"op","path","bones"}}
        if op not in fields or set(action)!=fields[op]:raise ValueError("Native action fields do not match operation")
        path(action["path"])
        if op=="set":values(action["value"])
        if op=="define_armature_bones":validate_armature_bones(action["bones"])
        if op=="call":
            if action["method"] not in METHODS or not isinstance(action["args"],list) or not isinstance(action["kwargs"],dict):
                raise ValueError("Unsupported native data method")
            if action["as"] is not None and (not isinstance(action["as"],str) or not action["as"].isidentifier() or action["as"].startswith("_")):
                raise ValueError("Native result identity must be a public identifier")
            values(action["args"])
            for key,value in action["kwargs"].items():
                if not isinstance(key,str) or key.startswith("_"):raise ValueError("Invalid native keyword")
                values(value)
        if op=="list" and (type(action["offset"]) is not int or action["offset"]<0
            or type(action["limit"]) is not int or not 1<=action["limit"]<=256):raise ValueError("Invalid collection page")
    if not isinstance(job["renders"],list) or len(job["renders"])>10000:raise ValueError("Native render budget exceeded")
    for item in job["renders"]:
        if (not isinstance(item,dict) or set(item)!={"scene","frame","format"} or not isinstance(item["scene"],str)
            or type(item["frame"]) is not int or item["format"] not in ("png","exr32")):
            raise ValueError("Native renders require scene, original integer frame and png/exr32")
    # JSON round trip rejects NaN/infinity as well as non-JSON values.
    if len(json.dumps(job,allow_nan=False).encode())>16*1024*1024:raise ValueError("Native job exceeds host byte budget")
    return job


def digest(path):
    with Path(path).open("rb") as stream:return hashlib.file_digest(stream,"sha256").hexdigest()


def verify_motion_bundle(path):
    with zipfile.ZipFile(path) as bundle:
        infos=bundle.infolist();names=[x.filename for x in infos]
        if len(names)!=len(set(names)) or len(names)>10005 or sum(x.file_size for x in infos)>8*1024**3:
            raise ValueError("Native bundle exceeds unique member/size budget")
        if any(Path(n).is_absolute() or ".." in Path(n).parts for n in names):raise ValueError("Unsafe native bundle path")
        report=json.loads(bundle.read("receipt.json"))
        if report.get("version")!=VERSION or set(names)!={"receipt.json",*report["members"]} or "project.blend" not in report["members"]:
            raise ValueError("Native bundle manifest mismatch")
        for name,expected in report["members"].items():
            h=hashlib.sha256()
            with bundle.open(name) as stream:
                for chunk in iter(lambda:stream.read(1024*1024),b""):h.update(chunk)
            if h.hexdigest()!=expected:raise ValueError("Native project/member identity changed")
        with bundle.open("project.blend") as stream:
            if not stream.read(12).startswith(b"BLENDER"):raise ValueError("Not a native uncompressed Blender project")
        if not isinstance(report.get("engine_version"),str):raise ValueError("No actual Blender engine identity")
    return report


def run_motion_project(job_path,workspace,target,*,timeout=3600):
    root=Path(workspace).resolve();source=Path(job_path).resolve();dest=Path(target)
    data=source.read_bytes()
    job=validate_motion_job(json.loads(data))
    if dest.exists():raise FileExistsError("Native project publication cannot overwrite a version")
    binary=shutil.which("blender")
    if binary is None:raise RuntimeError("Install native Blender 4.5 LTS or newer on the BODY host")
    version=subprocess.check_output([binary,"--version"],text=True,timeout=15).splitlines()[0]
    import re
    match=re.search(r"Blender (\d+)\.(\d+)",version)
    if not match or tuple(map(int,match.groups()))<(4,5):raise RuntimeError("Native motion projects require Blender 4.5+")
    with tempfile.TemporaryDirectory(prefix="zx7-native-motion-") as tmp:
        stage=Path(tmp);base=None;input_identity=None
        if job["project"] is not None:
            relative=Path(job["project"]);original=(root/relative).resolve()
            if relative.is_absolute() or ".." in relative.parts or not original.is_relative_to(root):raise ValueError("Native project escaped workspace")
            from .body_publication import require_published_source
            approved=require_published_source(original,"body.motion_project")
            # Operate only on the copied, reverified immutable input snapshot.
            sealed=stage/"input.zxmotion";shutil.copyfile(original,sealed)
            verify_motion_bundle(sealed);input_identity=digest(sealed)
            if input_identity!=approved:raise ValueError("Native parent changed after provenance verification")
            with zipfile.ZipFile(sealed) as bundle:base=stage/"input.blend";base.write_bytes(bundle.read("project.blend"))
        request=stage/"request.json";request.write_bytes(data)
        output=stage/"result";output.mkdir()
        args=[binary,"--background","--factory-startup","--disable-autoexec","--threads","2",
              "--python-exit-code","1","--python",str(Path(__file__).with_name("body_motion_worker.py")),"--",
              str(request),str(output)]
        if base:args.append(str(base))
        completed=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=timeout)
        if completed.returncode:raise RuntimeError("Native Blender transaction failed: "+completed.stdout[-6000:])
        native=json.loads((output/"native.json").read_text())
        members={p.name:digest(p) for p in output.iterdir() if p.is_file()}
        report={"version":VERSION,"engine_version":native["engine_version"],"job_sha256":hashlib.sha256(data).hexdigest(),
                "parent_bundle_sha256":input_identity,"members":members,"native":native,
                "model_inference_performed":False,"artistic_quality_approved":False}
        # Recheck original custody before final publication.
        if source.read_bytes()!=data:raise ValueError("Native job changed during rendering")
        if job["project"] and digest(original)!=input_identity:raise ValueError("Native source project changed during transaction")
        dest.parent.mkdir(parents=True,exist_ok=True)
        staged=stage/"publish.zxmotion"
        with zipfile.ZipFile(staged,"w",compression=zipfile.ZIP_STORED) as archive:
            for p in output.iterdir():archive.write(p,p.name)
            archive.writestr("receipt.json",json.dumps(report,sort_keys=True))
        verify_motion_bundle(staged)
        # Build on the destination filesystem before publishing. In particular,
        # process death during the copy must not expose a partial .zxmotion.
        # The hardlink is exclusive: never replace another owner's version.
        with tempfile.TemporaryDirectory(prefix=".zx7-native-publish-",dir=dest.parent) as publish:
            prepared=Path(publish)/"complete.zxmotion"
            with staged.open("rb") as incoming,prepared.open("xb") as stream:
                shutil.copyfileobj(incoming,stream)
                stream.flush()
                os.fsync(stream.fileno())
            if digest(prepared)!=digest(staged):
                raise ValueError("Native project changed during publication copy")
            os.link(prepared,dest)
            from .body_publication import sync_published_file
            sync_published_file(dest)
    return report


def export_motion_media(bundle_path,target,*,fps):
    from .body_publication import require_published_source
    approved=require_published_source(bundle_path,"body.motion_project")
    dest=Path(target)
    # Even direct callers must never observe a half-encoded published movie.
    if dest.exists() or dest.is_symlink():raise FileExistsError("Native media output already exists")
    if type(fps) is not int or not 1<=fps<=240:raise ValueError("Explicit integer delivery fps must be 1..240")
    suffix=dest.suffix.lower()
    if suffix not in (".png",".mp4"):raise ValueError("Native delivery supports png/mp4")
    # Stage on the output filesystem. Exclusive hardlink publishes only a
    # completed inode, rejects concurrent writers and needs no overwrite.
    with tempfile.TemporaryDirectory(prefix=".zx7-motion-export-",dir=dest.parent) as tmp:
        root=Path(tmp)
        sealed=root/"source.zxmotion";shutil.copyfile(bundle_path,sealed)
        if digest(sealed)!=approved:raise ValueError("Native export source changed after provenance verification")
        report=verify_motion_bundle(sealed);frames=report["native"]["renders"]
        if not frames or any(x["format"]!="png" for x in frames):raise ValueError("Media export needs authored PNG render order")
        with zipfile.ZipFile(sealed) as bundle:
            for i,frame in enumerate(frames):
                (root/f"frame_{i:06d}.png").write_bytes(bundle.read(frame["file"]))
        encoded=root/("encoded"+suffix)
        if suffix==".png":
            if len(frames)!=1:raise ValueError("PNG delivery requires one authored frame")
            shutil.copyfile(root/"frame_000000.png",encoded)
        else:
            subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-n","-framerate",str(fps),
                "-i",str(root/"frame_%06d.png"),"-c:v","libx264","-crf","18","-pix_fmt","yuv420p",
                "-movflags","+faststart",str(encoded)],check=True,timeout=3600)
        if not encoded.is_file() or not encoded.stat().st_size:
            raise RuntimeError("Native media encoder produced no bytes")
        # Archive-member SHA checks prove the PNG input, not FFmpeg output.
        # Physically decode output and remeasure the complete frame clock
        # BEFORE exposing a new publication inode. No scripted model approval.
        try:
            if suffix==".png":
                subprocess.run(["ffmpeg","-hide_banner","-loglevel","error",
                    "-xerror","-nostdin","-i",str(encoded),
                    "-frames:v","1","-f","null","-"],
                    capture_output=True,check=True,timeout=120)
            else:
                from .production_qc import full_decode_inspection
                from .precision_retime import _verify_decoded_frame_clock
                report_check=full_decode_inspection(encoded,
                    expected={"duration_seconds":len(frames)/fps},max_seconds=3600)
                if not report_check["technical_delivery_verified"]:
                    raise ValueError("Native encoded movie failed full decoder inspection: "+
                        repr(report_check["delivery_mismatches"]))
                _verify_decoded_frame_clock(encoded,Fraction(fps,1),len(frames))
        except (ValueError,OSError,subprocess.CalledProcessError,
                subprocess.TimeoutExpired) as exc:
            raise ValueError("Native media cannot be published without real decode proof") from exc
        # The encoded inode and final directory entry must both be durable
        # before an API caller sees a successful native export.
        with encoded.open("rb") as encoded_file:
            os.fsync(encoded_file.fileno())
        os.link(encoded,dest)
        from .body_publication import sync_published_file
        sync_published_file(dest)
    return report
