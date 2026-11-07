"""Opt-in real NVIDIA connectivity smoke; no asset upload, no secrets in output.

Run only with a trusted NVIDIA_API_KEY environment variable. The remote model
genuinely selects the JSON response; this is a protocol smoke, not an NLE test.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time

from studio_next.nvidia_model import NvidiaCreativeModel, NvidiaModelSettings

SYSTEM = (
    "You are a protocol compatibility tester. Return strictly one JSON object "
    "with exactly two fields: protocol equal to 'zx7-nvidia-smoke-v1' and "
    "accepted equal to true. Do not add markdown, explanation or other fields."
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-id", default="nvidia/nemotron-3.5-super-vl-120b-a12b")
    args = parser.parse_args(argv)
    model = NvidiaCreativeModel(
        NvidiaModelSettings(model_id=args.model_id, max_tokens=128,
                            timeout_seconds=90), system_prompt=SYSTEM)
    started = time.monotonic()
    decision = model.decide({"challenge": "Return the requested JSON protocol handshake.",
                             "contains_private_media": False})
    elapsed = round(time.monotonic() - started, 3)
    expected = {"protocol": "zx7-nvidia-smoke-v1", "accepted": True}
    passed = decision == expected
    print(json.dumps({
        "provider": "nvidia",
        "model_id": args.model_id,
        "request_reached_real_provider_if_no_http_mock": True,
        "protocol_json_match": passed,
        "elapsed_seconds_observed": elapsed,
        "provider_reported_tokens": model.last_call_usage,
        "original_media_sent": False,
        "native_editor_actions_performed": 0,
        "professional_creative_quality_verified": False,
        "model_response_sha256": hashlib.sha256(
            json.dumps(decision, sort_keys=True, ensure_ascii=False,
                       allow_nan=False).encode("utf-8")).hexdigest(),
    }, ensure_ascii=False))
    if not passed:
        raise SystemExit("Provider returned a valid but nonconforming JSON protocol response")


if __name__ == "__main__":
    main()
