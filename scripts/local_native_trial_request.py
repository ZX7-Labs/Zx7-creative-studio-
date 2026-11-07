"""Admit one explicitly requested, self-hosted LOCAL neural editor experiment.

Only the versioned request controls the push-triggered free/public Ubuntu
CPU trial. Never accepts a remote model endpoint, private media, arbitrary
weights, shell input or an unbounded model turn count.
"""
from __future__ import annotations

import json
from pathlib import Path
import re


class LocalTrialRequestError(ValueError):
    """Invalid or unapproved local creative inference experiment."""


_ALLOWED = frozenset({"qwen3.5-2b", "qwen3.5-4b"})
_FIELDS = frozenset({
    "schema", "kind", "model_variant", "synthetic_only",
    "hosted_model_api", "private_media", "max_model_turns", "request_id",
})


def _strict_pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise LocalTrialRequestError("Duplicate request field")
        out[key] = value
    return out


def validate_local_trial_request(path: Path) -> str:
    path = Path(path)
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 2048:
        raise LocalTrialRequestError("No safe local editor trial request")
    try:
        request = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_strict_pairs)
    except (ValueError, UnicodeError) as exc:
        raise LocalTrialRequestError("Untrusted local trial request JSON") from exc
    if (type(request) is not dict or set(request) != _FIELDS or
            type(request["schema"]) is not int or request["schema"] != 1 or
            request["kind"] != "local-cpu-synthetic-native-editor-visual-revision" or
            type(request["model_variant"]) is not str or
            request["model_variant"] not in _ALLOWED or
            request["synthetic_only"] is not True or
            request["hosted_model_api"] is not False or
            request["private_media"] is not False or
            type(request["max_model_turns"]) is not int or
            request["max_model_turns"] != 48 or
            type(request["request_id"]) is not str or not
            re.fullmatch(r"[A-Za-z0-9_-]{8,80}", request["request_id"])):
        raise LocalTrialRequestError("Invalid local neural model, media or budget")
    return request["model_variant"]


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request_file", type=Path)
    args = parser.parse_args()
    # One constrained choice is all that can cross into GitHub step env.
    print(validate_local_trial_request(args.request_file))


if __name__ == "__main__":
    main()
