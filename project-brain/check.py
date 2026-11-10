"""Offline, source-only canonical project brain contract. No model/API/network calls."""
from __future__ import annotations
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
REQUIRED = (
    "README.md", "BRIEF.md", "STATE.md", "DECISIONS.md",
    "RISKS.md", "PROJECT_MAP.md", "EVIDENCE/INDEX.md",
    "EVIDENCE/2026-11-10-INHERIT.md",
)
SENSITIVE = (
    re.compile(r"nvapi-[A-Za-z0-9_-]{20,}"),
    re.compile(r"sk-proj-[A-Za-z0-9_-]{16,}"),
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
    re.compile(r"NVIDIA_API_KEY\s*[:=]\s*(?!<|\{|\$)[A-Za-z0-9_-]{20,}"),
)
LINK = re.compile(r"(?<!!)\[[^\]\n]+\]\(([^)]+)\)")


def validate(root: pathlib.Path = ROOT) -> list[str]:
    """Return bounded factual filesystem/format failures without escaping root."""
    root = pathlib.Path(root)
    errors: list[str] = []
    for relative in REQUIRED:
        path = root / relative
        if path.is_symlink() or not path.is_file():
            errors.append(f"missing_or_symlink: {relative}")
            continue
        if path.stat().st_size > (14_000 if relative == "STATE.md" else 40_000):
            errors.append(f"too_large: {relative}")
            continue
        try:
            data = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            errors.append(f"not_utf8: {relative}")
            continue
        if not data.startswith("# "):
            errors.append(f"missing_heading: {relative}")
        for pattern in SENSITIVE:
            if pattern.search(data):
                errors.append(f"sensitive_material: {relative}")
                break
        for match in LINK.finditer(data):
            target = match.group(1).split("#", 1)[0].strip()
            if not target or target.startswith(("https://", "http://", "mailto:")):
                continue
            if target.startswith(("/", "~", "file:", "sandbox:")):
                errors.append(f"nonportable_link: {relative}")
                continue
            resolved = (path.parent / target).resolve()
            if not resolved.is_relative_to(root.parent.resolve()) or not resolved.is_file():
                errors.append(f"broken_or_escaping_link: {relative} -> {target}")
    state = root / "STATE.md"
    if state.is_file() and not state.is_symlink():
        text = state.read_text(encoding="utf-8")
        if not re.search(r"\b[0-9a-f]{40}\b", text):
            errors.append("state_lacks_exact_source_sha")
        if "Refresh" not in text and "refresh" not in text:
            errors.append("state_lacks_live_refresh_warning")
    return errors


if __name__ == "__main__":
    problems = validate()
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        raise SystemExit(1)
    print("Project brain offline contract: PASS")
