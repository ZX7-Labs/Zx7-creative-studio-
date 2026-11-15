"""Offline, source-only canonical project brain contract. No model/API/network calls."""
from __future__ import annotations
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
REQUIRED = (
    "README.md", "BRIEF.md", "STATE.md", "DECISIONS.md",
    "RISKS.md", "PROJECT_MAP.md", "EVIDENCE/INDEX.md",
    "EVIDENCE/2026-11-10-INHERIT.md",
    "EVIDENCE/2026-11-12-G0-COVERAGE.md",
    "EVIDENCE/FAILURE_REGISTER.md",
    "STATE-2026-11-15-ARCHIVE.md",
    "EXECUTION_LEDGER.json",
    "../docs/ZX7_CREATIVE_STUDIO_MASTER_PLAN.md",
    "../docs/BUILD_BLUEPRINT.md",
    "../docs/DOCUMENT_MAP.md",
)
SENSITIVE = (
    re.compile(r"nvapi-[A-Za-z0-9_-]{20,}"),
    re.compile(r"sk-proj-[A-Za-z0-9_-]{16,}"),
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
    re.compile(r"NVIDIA_API_KEY\s*[:=]\s*(?!<|\{|\$)[A-Za-z0-9_-]{20,}"),
)
LINK = re.compile(r"(?<!!)\[[^\]\n]+\]\(([^)]+)\)")


def _review_receipt_is_structured(value: object) -> bool:
    """Only check a source-linked receipt shape; this never validates a reviewer."""
    if not isinstance(value, dict):
        return False
    return (
        re.fullmatch(r"[0-9a-f]{40}", str(value.get("source_sha", ""))) is not None
        and str(value.get("report_url", "")).startswith(
            "https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/"
        )
        and bool(str(value.get("reviewer", "")).strip())
        and bool(str(value.get("scope", "")).strip())
    )


def _model_retest_receipt_is_structured(value: object, failure_id: str) -> bool:
    """Gate a claimed real-model retest on an attributable comparable-run shape."""
    if not isinstance(value, dict):
        return False
    return (
        re.fullmatch(r"[0-9a-f]{40}", str(value.get("source_sha", ""))) is not None
        and str(value.get("run_url", "")).startswith(
            "https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/"
        )
        and value.get("same_task_as") == failure_id
        and re.fullmatch(r"[0-9a-f]{64}", str(value.get("artifact_sha256", "")))
        is not None
    )


def validate(root: pathlib.Path = ROOT) -> list[str]:
    """Return bounded factual filesystem/format failures without escaping root."""
    root = pathlib.Path(root)
    errors: list[str] = []
    for relative in REQUIRED:
        path = root / relative
        if path.is_symlink() or not path.is_file():
            errors.append(f"missing_or_symlink: {relative}")
            continue
        maximum = (14_000 if relative == "STATE.md" else
                   240_000 if relative in ("DECISIONS.md", "EVIDENCE/INDEX.md") else
                   160_000 if relative.startswith("../docs/") else 40_000)
        if path.stat().st_size > maximum:
            errors.append(f"too_large: {relative}")
            continue
        try:
            data = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            errors.append(f"not_utf8: {relative}")
            continue
        if not relative.endswith(".json") and not data.startswith("# "):
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
    # Structural traceability only: this cannot certify semantic completeness,
    # native execution, safety, or artistic quality. A missing/doubled ID is
    # nevertheless a cheap, objective regression in the owner-approved scope.
    plan = root / "../docs/ZX7_CREATIVE_STUDIO_MASTER_PLAN.md"
    fixture = root / "EVIDENCE/2026-11-12-G0-COVERAGE.md"
    coverage = (
        ("A-L", plan, r"^\|\s*\*\*([A-L])\s*[—–-]", list("ABCDEFGHIJKL")),
        ("T01-T24", plan, r"^\|\s*(T\d{2})\s*\|",
         [f"T{i:02d}" for i in range(1, 25)]),
        ("F01-F14", fixture, r"^\|\s*(F\d{2})\s*\|",
         [f"F{i:02d}" for i in range(1, 15)]),
    )
    for label, source, pattern, expected in coverage:
        if source.is_symlink() or not source.is_file() or source.stat().st_size > 160_000:
            continue  # Required-file scanner reports these earlier.
        try:
            found = re.findall(pattern, source.read_text(encoding="utf-8"), re.M)
        except (OSError, UnicodeError):
            continue  # Required-file scanner reports this earlier.
        if sorted(found) != sorted(expected):
            errors.append(f"missing_or_duplicate_coverage: {label}")

    state = root / "STATE.md"
    if state.is_file() and not state.is_symlink():
        text = state.read_text(encoding="utf-8")
        if not re.search(r"\b[0-9a-f]{40}\b", text):
            errors.append("state_lacks_exact_source_sha")
        if "Refresh" not in text and "refresh" not in text:
            errors.append("state_lacks_live_refresh_warning")

    # Structure only, NOT a certification of factual/source/semantic correctness.
    # Verify source-linked evidence before claiming acceptance; never block
    # future independently reviewed success just because the baseline was open.
    ledger_path = root / "EXECUTION_LEDGER.json"
    if ledger_path.is_file() and not ledger_path.is_symlink():
        try:
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeError, OSError):
            errors.append("invalid_execution_ledger_json")
        else:
            if not isinstance(ledger, dict) or ledger.get("schema_version") != "zx7.execution-ledger.v1":
                errors.append("invalid_execution_ledger_schema")
            else:
                domains = ledger.get("domains", [])
                if (not isinstance(domains, list) or
                        sorted(d.get("id", "") for d in domains if isinstance(d, dict)) != list("ABCDEFGHIJKL") or
                        len(domains) != 12):
                    errors.append("invalid_execution_ledger_domain_coverage")
                else:
                    for domain in domains:
                        status = domain.get("independent_field_acceptance")
                        if status not in ("NOT_ACCEPTED", "ACCEPTED"):
                            errors.append("unsupported_execution_ledger_field_acceptance")
                            break
                        if (status == "ACCEPTED" and
                                not _review_receipt_is_structured(domain.get("acceptance_evidence"))):
                            # An acceptance can advance with a linkable source and
                            # reviewer. Shape is NOT proof the reviewer actually ran.
                            errors.append("unsupported_execution_ledger_field_acceptance")
                            break
                snapshot = ledger.get("snapshot", {})
                if not isinstance(snapshot, dict) or not re.fullmatch(
                    r"[0-9a-f]{40}", str(snapshot.get("github_main_at_audit", ""))
                ):
                    errors.append("invalid_execution_ledger_source_baseline")
                failures = ledger.get("failures", [])
                if not isinstance(failures, list) or len(failures) < 3:
                    errors.append("invalid_execution_ledger_failure_inventory")
                else:
                    ids = [f.get("id") for f in failures if isinstance(f, dict)]
                    if len(ids) != len(failures) or len(set(ids)) != len(ids):
                        errors.append("invalid_execution_ledger_failure_ids")
                    for f in failures:
                        if (not isinstance(f, dict) or
                                not isinstance(f.get("run"), int) or
                                not str(f.get("run_url", "")).startswith("https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/") or
                                not f.get("source_or_fix") or
                                not f.get("post_fix_real_model_retest")):
                            errors.append("invalid_execution_ledger_failure_evidence")
                            break
                        if (f.get("kind") == "GENUINE_MODEL" and
                                f.get("post_fix_real_model_retest") == "PASSED" and
                                not _model_retest_receipt_is_structured(
                                    f.get("post_fix_retest_evidence"), f["id"]
                                )):
                            # Do not block future genuine progress forever; reject
                            # bare success without a comparable model run receipt.
                            errors.append("unreviewed_execution_ledger_neural_success")
                            break
                gates = ledger.get("open_gates", [])
                g1 = next((g for g in gates
                           if isinstance(g, dict) and g.get("id") == "G1-AUTONOMY"), None) \
                    if isinstance(gates, list) else None
                if (g1 is None or
                        g1.get("state") not in ("OPEN_CRITICAL", "IN_PROGRESS", "ACCEPTED") or
                        (g1.get("state") == "ACCEPTED" and
                         not _review_receipt_is_structured(g1.get("acceptance_evidence"))) or
                        (g1.get("state") == "IN_PROGRESS" and
                         not str(g1.get("progress_evidence", "")).startswith(
                             "https://github.com/ZX7-Labs/Zx7-creative-studio-/"
                         ))):
                    errors.append("invalid_execution_ledger_g1_priority")

    blueprint = root / "../docs/BUILD_BLUEPRINT.md"
    if blueprint.is_file() and not blueprint.is_symlink():
        contents = blueprint.read_text(encoding="utf-8")
        if (not all(f"G1-0{i}" in contents for i in range(1, 8)) or
                "CANDIDATE / G2" not in contents or
                "Fixed goal ≠ fixed technique" not in contents):
            errors.append("invalid_blueprint_fixed_vs_hypothesis_boundary")

    return errors


if __name__ == "__main__":
    problems = validate()
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        raise SystemExit(1)
    print("Project brain offline contract: PASS")
