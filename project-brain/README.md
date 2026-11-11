# ZX7 Project Brain — durable engineering continuity

**Read this after [AGENTS.md](../AGENTS.md).** This is the versioned, repository-backed memory for ZX7 Creative Studio across chat sessions, machines and agents. A disposable chat or sandbox is **not** a source of truth.

## What owns which facts?

1. [CAPABILITIES.md](../CAPABILITIES.md) is the complete A–L product and acceptance contract. [ENGINEERING_STANDARD.md](../ENGINEERING_STANDARD.md) and [AGENTS.md](../AGENTS.md) own the enduring engineering rules.
2. [BRIEF.md](BRIEF.md) captures founder intent, the current provider-development strategy and immutable quality/safety constraints. Modify only for an explicit requirement delta; preserve prior intent in [DECISIONS.md](DECISIONS.md).
3. [STATE.md](STATE.md) is the **single current working snapshot**: last verified integration, exact outstanding PRs/runs, causal blocker, next evidence gate. It is time-stamped and MUST be refreshed against live GitHub before work.
4. [DECISIONS.md](DECISIONS.md) is an append-only decision ledger; supersede by adding a new decision rather than rewriting history.
5. [RISKS.md](RISKS.md) lists live failure modes, verification status, and next falsifiable test; close or supersede a risk only with evidence.
6. [PROJECT_MAP.md](PROJECT_MAP.md) records stable architecture and accessible/unavailable sources.
7. [EVIDENCE/INDEX.md](EVIDENCE/INDEX.md) links reproducible positive **and negative** tests, exact run/commit IDs and the original Inherit Mode snapshot. Artifact links may expire; persistent conclusions remain in Git history.
8. [ZX7 Creative Studio Master Plan](../docs/ZX7_CREATIVE_STUDIO_MASTER_PLAN.md) consolidates the owner's chronological product/architecture reasoning, original AI engineering team and agent-memory/handoff design, replaceable Brain–BODY controls, hybrid creative-medium hypotheses, live human collaboration and A–L/gates. It is a **design atlas**, not a second current STATE or a supersession of canonical CAPABILITIES. The concrete [G0 F01–F14 fixture map](EVIDENCE/2026-11-12-G0-COVERAGE.md) preserves test definitions; statuses remain unpassed until real evidence exists.

The large [docs/continuity/STATUS.md](../docs/continuity/STATUS.md) is retained **only as historical evidence**. It is not a second current-state document. Use [docs/continuity/WORKING_AGREEMENT.md](../docs/continuity/WORKING_AGREEMENT.md) for the engineering method.

## Session protocol (no manual founder re-brief)

**At session start:** read `AGENTS.md`, this README, `BRIEF.md`, `STATE.md`, `DECISIONS.md`, `RISKS.md`, `PROJECT_MAP.md` and the relevant evidence. Refresh current `main`, open PRs, exact-head CI and active trial status using GitHub, not the frozen snapshot. Preserve uncommitted changes and avoid duplicate jobs.

**During work:** use a separate branch, make evidence-led targeted changes, run independent/relevant tests, state failures openly. The founder's latest instruction is a DELTA; do not restart or silently contradict earlier decisions.

**At each meaningful checkpoint:** update `STATE.md` (replace stale snapshot, do not append a diary), append decision IDs only when a decision changed, update active risks and the evidence index with reproducible links. In the *same reviewable PR* update any instructions that became inaccurate. Review the diff for secrets, private path/media/credentials and misleading green claims. Require CI and human/independent technical scrutiny of source changes.

**On a new chat:** the founder can say “Continue ZX7: read the repository project-brain.” No need to paste the old history when the repository is accessible. A new model/session must still fetch it; neither ChatGPT memory nor this repository auto-executes work.

## Durability and privacy

Git commits/PRs supply a durable, attributed, versioned history with ordinary diff/rollback, subject to repository access and retention. Never force-push or delete project history as a memory-maintenance shortcut. Do **not** commit local scratch ZIPs, API credentials, internal prompts, owner-uploaded private media, arbitrary chat transcripts, or the founder's original personal PDF to this public repository. Summarize owner intent in BRIEF; refer to sensitive originals only outside public Git. GitHub Actions artifacts can expire: cite run IDs and durable tests, and note any unavailable bytes.

Run `python project-brain/check.py` and `python -m unittest discover -s project-brain -p 'test_check.py'` after changes. Dedicated offline CI verifies these instructions without calling hosted models.
