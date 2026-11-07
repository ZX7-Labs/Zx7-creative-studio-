"""One bounded NVIDIA forced-function-call protocol smoke, no media or editor.

This checks the hosted endpoint's tool-call shape, never executes a native tool.
"""
from __future__ import annotations

import json
from studio_next.nvidia_model import NvidiaModelSettings
from studio_next.nvidia_tool_model import NvidiaToolCreativeModel


def main():
    model = NvidiaToolCreativeModel(
        NvidiaModelSettings(max_tokens=160, timeout_seconds=60),
        system_prompt=(
            "This is a tool-call transport diagnostic. You are not controlling "
            "an editor. You MUST call zx7_select_next_creative_action exactly "
            "once with {action:'search',arguments:{query:'project creator'},"
            "reason:'Identify the native project creation tool'}. Do not emit "
            "prose or other actions."
        ))
    decision = model.decide({
        "available_actions": ["search"],
        "compact_tool_catalog": True,
        "purpose": "Verify genuine provider function-call envelope only",
    })
    good = (
        type(decision) is dict and set(decision) == {
            "action", "arguments", "reason"
        } and decision["action"] == "search" and
        type(decision["arguments"]) is dict and
        decision["arguments"].get("query") == "project creator" and
        type(decision["reason"]) is str and bool(decision["reason"].strip())
    )
    print(json.dumps({
        "actual_provider": "nvidia",
        "model": model.settings.model_id,
        "forced_function_call_envelope_accepted": good,
        "provider_reported_usage": model.last_call_usage,
        "media_uploaded": False,
        "native_tools_dispatched": 0,
    }, ensure_ascii=False))
    if not good:
        raise SystemExit("Provider tool-choice protocol does not meet host bounds")


if __name__ == "__main__":
    main()
