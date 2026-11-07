"""Strict, cost-bounded authorization for original NVIDIA -> film rendering.

A request file never contains credentials, preselected music or creative art.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from scripts.nvidia_smoke_request import _unique_json, SmokeRequestError

_FIELDS=frozenset({"schema","kind","model_id","synthetic_only",
                   "allow_external_stock_media","max_model_attempts","request_id"})
_MODEL="nvidia/nemotron-3.5-super-vl-120b-a12b"


def validate_request(path:Path):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<=2048:
        raise SmokeRequestError("No bounded authorized original-film request")
    try:
        req=json.loads(path.read_text(encoding="utf-8"),
                       object_pairs_hook=_unique_json)
    except (UnicodeError,ValueError):
        raise SmokeRequestError("Invalid original-film request JSON") from None
    if (type(req) is not dict or set(req)!=_FIELDS or
            type(req["schema"]) is not int or req["schema"]!=1 or
            req["kind"]!="nvidia-original-model-authored-film" or
            req["model_id"]!=_MODEL or
            req["synthetic_only"] is not True or
            req["allow_external_stock_media"] is not False or
            type(req["max_model_attempts"]) is not int or
            req["max_model_attempts"]!=3 or
            type(req["request_id"]) is not str or not
            re.fullmatch(r"[A-Za-z0-9_-]{8,80}",req["request_id"])):
        raise SmokeRequestError("Unauthorized model, scope, cost or original media")
    return req


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("path",type=Path)
    a=p.parse_args(argv)
    req=validate_request(a.path)
    print("ADMITTED original non-stock film proof:",req["request_id"])


if __name__=="__main__": main()
