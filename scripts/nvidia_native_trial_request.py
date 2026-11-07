"""Strict reviewed consent for a bounded synthetic-only cloud-native experiment.

Validation runs before build or any cloud credential is exposed.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re

from scripts.nvidia_smoke_request import _unique_json, SmokeRequestError
from scripts.run_nvidia_native_trial import _ALLOWED_MODEL


_FIELDS = frozenset({"schema", "kind", "model_id", "synthetic_only",
                    "cloud_synthetic_frames_allowed", "max_turns", "request_id"})


def validate_native_trial_request(path: Path) -> str:
    path = Path(path)
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 2048:
        raise SmokeRequestError("No safe explicit native-editor evaluation request")
    try:
        value = json.loads(path.read_text(encoding="utf-8"),
                           object_pairs_hook=_unique_json)
    except (ValueError, UnicodeError):
        raise SmokeRequestError("Invalid native-editor evaluation request JSON") from None
    if (type(value) is not dict or set(value) != _FIELDS or
            type(value["schema"]) is not int or value["schema"] != 1 or
            value["kind"] != "nvidia-synthetic-native-editor-visual-revision" or
            value["model_id"] != _ALLOWED_MODEL or
            value["synthetic_only"] is not True or
            value["cloud_synthetic_frames_allowed"] is not True or
            type(value["max_turns"]) is not int or value["max_turns"] != 40 or
            type(value["request_id"]) is not str or not
            re.fullmatch(r"[A-Za-z0-9_-]{8,80}", value["request_id"])):
        raise SmokeRequestError("Unapproved model, media egress or unbounded native trial")
    return value["model_id"]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("request_file", type=Path)
    args = p.parse_args(argv)
    print("Native editor evaluation admitted for model:",
          validate_native_trial_request(args.request_file))


if __name__ == "__main__":
    main()
