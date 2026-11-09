#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Compatibility entry for the installed, canonical native editor session."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from studio_next.native_editor_session import (
    main, run_native_session, build_parser, cli, editor_runtime_path,
    native_decision_model, native_editor_child_environment,
    native_session_grants,
    pinned_electron_marker_previews, trial_machine_contracts,
    _PINNED_MCP_PREVIEW_COMMIT, _PINNED_MARKER_PREVIEWS,
)

if __name__ == "__main__":
    raise SystemExit(cli())
