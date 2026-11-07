"""Validate an explicit, audited, credential-free NVIDIA smoke request.

The output is a single GitHub Actions environment assignment. Never
evaluate model input, execute a remote request or read a secret here.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

_ALLOWED_VARIANTS = frozenset({"nemotron-super-vl", "qwen3.5-122b"})
_EXACT_FIELDS = frozenset({
    "schema", "kind", "model_variant", "media_upload",
    "max_tokens", "request_id",
})


class SmokeRequestError(ValueError):
    """No API call has been made."""


def _unique_json(pairs):
    values = {}
    for key, value in pairs:
        if key in values:
            raise SmokeRequestError("Duplicate field in requested cloud inference")
        values[key] = value
    return values


def validate_smoke_request(path: Path) -> str:
    path = Path(path)
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 2048:
        raise SmokeRequestError("Request missing, linked or outside 2 KiB limit")
    try:
        request = json.loads(path.read_text(encoding="utf-8"),
                             object_pairs_hook=_unique_json)
    except (UnicodeError, ValueError) as exc:
        raise SmokeRequestError("Invalid smoke request JSON") from None
    if (type(request) is not dict or set(request) != _EXACT_FIELDS or
            type(request["schema"]) is not int or request["schema"] != 1 or
            request["kind"] != "nvidia-no-media-protocol-smoke" or
            type(request["model_variant"]) is not str or
            request["model_variant"] not in _ALLOWED_VARIANTS or
            request["media_upload"] is not False or
            type(request["max_tokens"]) is not int or request["max_tokens"] != 128 or
            type(request["request_id"]) is not str or not
            re.fullmatch(r"[A-Za-z0-9_-]{8,80}", request["request_id"])):
        raise SmokeRequestError("Only bounded, no-media NVIDIA protocol tests are admitted")
    return request["model_variant"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request_file", type=Path)
    args = parser.parse_args(argv)
    # The admitted variant is an exact internal allowlisted token. No newline,
    # shell expression, secret or arbitrary user-supplied string is emitted.
    print("MODEL_VARIANT=" + validate_smoke_request(args.request_file))


if __name__ == "__main__":
    main()
