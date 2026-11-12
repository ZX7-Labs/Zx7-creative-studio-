"""Admission for a NEW, explicitly reviewed, synthetic-only NVIDIA A/V trial.

No inference, API call, media inspection or secret access. The historical
visual-only request is spent and is deliberately not accepted for A/V.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from scripts.nvidia_smoke_request import SmokeRequestError, _unique_json
from scripts.run_nvidia_native_trial import _ALLOWED_MODEL, _TRIAL_MAX_TURNS


_FIELDS = frozenset({
    "schema", "kind", "model_id", "synthetic_only",
    "cloud_synthetic_frames_allowed", "cloud_numerical_audio_diagnostics_allowed",
    "owner_media_allowed", "max_turns", "request_id", "run_authorized",
})
_KIND = "nvidia-synthetic-native-audiovisual-revision"


def validate_av_trial_request(path: Path, *, dispatch_request_id: str) -> str:
    """Require an exact, uniquely identified new grant before paid model access.

    Human-reviewed Git content plus matching explicit workflow_dispatch input
    is required. A request is NOT cryptographic authorisation or a durable
    one-use token; GitHub access policy and manual oversight remain essential.
    """
    if (type(dispatch_request_id) is not str or not
            re.fullmatch(r"[A-Za-z0-9_-]{16,80}", dispatch_request_id)):
        raise SmokeRequestError("Missing explicit bounded audiovisual dispatch identity")
    path = Path(path)
    if (path.is_symlink() or not path.is_file() or not
            0 < path.stat().st_size <= 2048):
        raise SmokeRequestError("No safe new audiovisual model request")
    try:
        value = json.loads(path.read_text(encoding="utf-8"),
                           object_pairs_hook=_unique_json)
    except (ValueError, UnicodeError):
        raise SmokeRequestError("Invalid new audiovisual model request JSON") from None
    if (type(value) is not dict or set(value) != _FIELDS or
            type(value["schema"]) is not int or value["schema"] != 1 or
            value["kind"] != _KIND or value["model_id"] != _ALLOWED_MODEL or
            value["synthetic_only"] is not True or
            value["cloud_synthetic_frames_allowed"] is not True or
            value["cloud_numerical_audio_diagnostics_allowed"] is not True or
            value["owner_media_allowed"] is not False or
            type(value["max_turns"]) is not int or
            value["max_turns"] != _TRIAL_MAX_TURNS or
            value["run_authorized"] is not True or
            type(value["request_id"]) is not str or
            value["request_id"] != dispatch_request_id):
        raise SmokeRequestError("A/V model request not newly approved for this exact dispatch")
    return value["model_id"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request_file", type=Path)
    parser.add_argument("--dispatch-request-id", required=True)
    args = parser.parse_args(argv)
    print("New synthetic A/V trial admitted:",
          validate_av_trial_request(
              args.request_file, dispatch_request_id=args.dispatch_request_id))


if __name__ == "__main__":
    main()
