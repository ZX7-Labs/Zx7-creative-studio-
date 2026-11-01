"""Standalone ZX7 creative BODY client: no ChatGPT, cloud or paid account.

Run with `python -m studio_next.body_client`. All operations target the
already-authenticated loopback production service, not remote web endpoints.
Job plans, film decisions and tool selection remain author/model-owned.

Arguments are real paths/tool IDs, never executable model-supplied commands.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import http.client
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import quote,urlsplit

from .media_vault import sha256_file

_ID=re.compile(r"^[A-Za-z0-9_-]{1,80}$")


def _local_address(endpoint):
    parsed=urlsplit(endpoint)
    if parsed.scheme!="http" or parsed.hostname not in ("127.0.0.1","localhost","::1") or (
            parsed.username or parsed.password or parsed.query or parsed.fragment or
            parsed.path not in ("","/") or not parsed.port):
        raise ValueError("ZX7 studio client connects only to an authenticated loopback service")
    return parsed.hostname,parsed.port


class ZX7BodyClient:
    def __init__(self,*,endpoint="http://127.0.0.1:8765",token=None):
        self.hostname,self.port=_local_address(endpoint)
        self.token=token if token is not None else os.getenv("ZX7_BODY_API_TOKEN","")
        if not isinstance(self.token,str) or len(self.token)<32:
            raise ValueError("Set the same 32+ character local body service token")

    def _open(self,method,path,*,body=None,content_type=None,headers=None):
        if not isinstance(path,str) or not path.startswith("/v1/"):
            raise ValueError("Local production client endpoint must use /v1/")
        if body is not None and not isinstance(body,(bytes,bytearray)) and not callable(getattr(body,"read",None)):
            raise TypeError("Local HTTP body requires binary bytes or a streaming original media file")
        connection=http.client.HTTPConnection(self.hostname,self.port,timeout=90)
        meta={"Authorization":"Bearer "+self.token,"Accept":"application/json",
              "Cache-Control":"no-store"}
        if content_type is not None:meta["Content-Type"]=content_type
        if headers:meta.update(headers)
        connection.request(method,path,body=body,headers=meta)
        reply=connection.getresponse()
        return connection,reply

    def request_json(self,method,path,payload=None,*,body=None,content_type=None,headers=None):
        if payload is not None:
            body=json.dumps(payload,ensure_ascii=False,allow_nan=False).encode("utf-8")
            content_type="application/json"
        connection,response=self._open(method,path,body=body,
                                       content_type=content_type,headers=headers)
        try:
            raw=response.read(4_200_000)
            if response.status not in (200,201,202):
                raise RuntimeError(f"Studio HTTP {response.status}: "+raw.decode("utf-8","replace")[:500])
            if len(raw)>=4_200_000:
                raise ValueError("Unbounded non-media response from creative service")
            return json.loads(raw.decode("utf-8"))
        finally:connection.close()

    def research(self, query, *, domain="all", media="all", limit=12):
        """All creative domains; host-authenticated free public metadata only.

        Does not import third-party media or certify the candidate's rights.
        """
        return self.request_json("POST", "/v1/research",
                                 {"query": query, "domain": domain,
                                  "media": media, "limit": limit})

    def tools(self):
        return self.request_json("GET","/v1/tools")

    def tool(self,tool_id):
        if not isinstance(tool_id,str) or not tool_id or "/" in tool_id:
            raise ValueError("Invalid registered creative tool identity")
        return self.request_json("GET","/v1/tools/"+quote(tool_id,safe=""))

    def submit(self,original_film_ir,workspace_id):
        if not _ID.fullmatch(workspace_id):
            raise ValueError("Invalid independent film workspace identity")
        path=Path(original_film_ir)
        plan=json.loads(path.read_text(encoding="utf-8"))
        return self.request_json("POST","/v1/jobs",
                  {"workspace_id":workspace_id,"film_ir":plan})

    def jobs(self):
        return self.request_json("GET","/v1/jobs")

    def retry(self,job_id):
        return self._job_control(job_id,"retry")

    def pause(self,job_id):
        return self._job_control(job_id,"pause")

    def resume(self,job_id):
        return self._job_control(job_id,"resume")

    def cancel(self,job_id):
        return self._job_control(job_id,"cancel")

    def _job_control(self,job_id,action):
        if not isinstance(job_id,str) or not _ID.fullmatch(job_id):
            raise ValueError("Invalid original body job")
        return self.request_json("POST","/v1/jobs/"+job_id+"/"+action,
                                 body=b"",headers={"Content-Length":"0"})

    def status(self,job_id):
        if not _ID.fullmatch(job_id):
            raise ValueError("Invalid physical studio job identity")
        return self.request_json("GET","/v1/jobs/"+job_id)

    def wait(self,job_id,*,poll_seconds=2,max_seconds=3600,sleep=None,clock=None):
        if not (0.1<=poll_seconds<=3600) or not (1<=max_seconds<=86400):
            raise ValueError("Finite operator-chosen polling and time budget required")
        monotonic=clock or time.monotonic
        pause=sleep or time.sleep
        deadline=monotonic()+max_seconds
        while monotonic()<deadline:
            status=self.status(job_id)
            if status["status"] in ("completed","blocked","failed","paused","cancelled"):
                return status
            pause(poll_seconds)
        raise TimeoutError("Original production job still in progress; saved work preserved")

    def upload(self,workspace_id,source,*,source_id,rights_evidence,mime):
        if not _ID.fullmatch(workspace_id):
            raise ValueError("Invalid destination project")
        original=Path(source)
        if not original.is_file():
            raise ValueError("Original owner media is missing")
        data_size=original.stat().st_size
        if not (0<data_size<=1024*1024*1024):
            raise ValueError("Owner upload exceeds current local endpoint budget")
        if not isinstance(source_id,str) or not source_id.strip() or (
                not isinstance(rights_evidence,str) or not rights_evidence.strip()):
            raise ValueError("Original media must carry explicit owner provenance")
        if not isinstance(mime,str) or not mime:
            raise ValueError("Original media MIME required")
        # Stream bounded source bytes instead of loading a 1GB 4K film
        # into RAM. HTTP Content-Length is explicit; no chunked uploads.
        # SHA verifies the same original file was received by the service.
        initial_sha=sha256_file(original)
        path=f"/v1/workspaces/{workspace_id}/assets/"+quote(original.name,safe="")
        with original.open("rb") as stream:
            receipt=self.request_json("POST",path,body=stream,
                content_type=mime,headers={
                "Content-Length":str(data_size),
                # HTTP headers are ASCII; source evidence can be authored in
                # Hindi or any UTF-8 language, without text corruption.
                "X-Source-Id-B64":base64.b64encode(
                    source_id.encode("utf-8")).decode("ascii"),
                "X-Rights-Evidence-B64":base64.b64encode(
                    rights_evidence.encode("utf-8")).decode("ascii")})
        if sha256_file(original)!=initial_sha or receipt.get("asset_id")!=initial_sha:
            raise RuntimeError("Uploaded original film differs from byte-verified source")
        return receipt

    def artifacts(self,job_id):
        if not _ID.fullmatch(job_id):
            raise ValueError("Invalid original production job")
        return self.request_json("GET",f"/v1/jobs/{job_id}/artifacts")

    def download(self,job_id,relative,output):
        if not _ID.fullmatch(job_id):
            raise ValueError("Invalid original production job")
        if (not isinstance(relative,str) or not relative or
                Path(relative).is_absolute() or any(p in ("..",".","") for p in
                relative.split("/")) or "\\" in relative):
            raise ValueError("Unsafe relative output movie path")
        dest=Path(output)
        if dest.exists():
            raise FileExistsError("Never overwrite an already accepted video/media artifact")
        dest.parent.mkdir(parents=True,exist_ok=True)
        path=f"/v1/jobs/{job_id}/artifacts/"+"/".join(
            quote(part,safe="") for part in relative.split("/"))
        connection,response=self._open("GET",path)
        staging=None
        try:
            if response.status!=200:
                raise RuntimeError(f"Original media download denied ({response.status}): "+
                                   response.read(512).decode("utf-8","replace"))
            expected=response.getheader("X-ZX7-SHA256","")
            length=int(response.getheader("Content-Length","0"))
            if not re.fullmatch(r"[0-9a-f]{64}",expected) or length<=0:
                raise ValueError("Real media reply missing content digest and physical byte size")
            fd,name=tempfile.mkstemp(prefix=".zx7-incomplete-",dir=dest.parent)
            staging=Path(name)
            hasher=hashlib.sha256()
            size=0
            with os.fdopen(fd,"wb") as out:
                while True:
                    chunk=response.read(min(1024*1024,max(1,length-size)))
                    if not chunk:break
                    hasher.update(chunk)
                    out.write(chunk)
                    size+=len(chunk)
                    if size>length:raise ValueError("Delivered media exceeds declared original file size")
                out.flush()
                os.fsync(out.fileno())
            if size!=length or hasher.hexdigest()!=expected:
                raise ValueError("Studio artifact differs from original saved media digest")
            if dest.exists():
                raise FileExistsError("Original accepted media already exists")
            os.link(staging,dest)
            return {"path":str(dest),"bytes":size,"sha256":expected,
                    "verified_download_of_actual_media":True}
        finally:
            connection.close()
            if staging is not None:staging.unlink(missing_ok=True)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api",default="http://127.0.0.1:8765")
    modes=parser.add_subparsers(dest="command",required=True)
    modes.add_parser("tools")
    p=modes.add_parser("describe");p.add_argument("tool_id")
    p=modes.add_parser("submit");p.add_argument("original_film_ir");p.add_argument("--workspace",required=True)
    modes.add_parser("jobs")
    for action in ("retry","pause","resume","cancel"):
        p=modes.add_parser(action);p.add_argument("job_id")
    p=modes.add_parser("status");p.add_argument("job_id")
    p=modes.add_parser("wait");p.add_argument("job_id");p.add_argument("--seconds",type=float,default=3600)
    p=modes.add_parser("artifacts");p.add_argument("job_id")
    p=modes.add_parser("download");p.add_argument("job_id");p.add_argument("source");p.add_argument("--out",required=True)
    p=modes.add_parser("upload");p.add_argument("source");p.add_argument("--workspace",required=True)
    p.add_argument("--source-id",required=True);p.add_argument("--rights-evidence",required=True)
    p.add_argument("--mime",required=True)
    args=parser.parse_args(argv)
    client=ZX7BodyClient(endpoint=args.api)
    if args.command=="tools":result=client.tools()
    elif args.command=="describe":result=client.tool(args.tool_id)
    elif args.command=="submit":result=client.submit(args.original_film_ir,args.workspace)
    elif args.command=="jobs":result=client.jobs()
    elif args.command in ("retry","pause","resume","cancel"):
        result=getattr(client,args.command)(args.job_id)
    elif args.command=="status":result=client.status(args.job_id)
    elif args.command=="wait":result=client.wait(args.job_id,max_seconds=args.seconds)
    elif args.command=="artifacts":result=client.artifacts(args.job_id)
    elif args.command=="download":result=client.download(args.job_id,args.source,args.out)
    else:result=client.upload(args.workspace,args.source,
        source_id=args.source_id,rights_evidence=args.rights_evidence,mime=args.mime)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=="__main__":main()
