# ZX7 — current engineering STATE

Snapshot taken: **2026-11-10 UTC**. Re-verify all live state before acting. This is not an automatic workflow or real-time dashboard.

## Known integrated source (at snapshot)

- Repo: https://github.com/ZX7-Labs/Zx7-creative-studio- ; branch `main`.
- Verified pre-continuity main commit: `76104b4f177ad1eb99e0cb17c8fee194d0d6193e` (one scoped NVIDIA trial request after source readiness fix). This document's own commit will change the main head; never treat this SHA as continuously current.
- Merged #285: pinned Electron image-sequence compatibility; #286: source Ubuntu native installer and scripted create/export/reopen/revise proof; #287: older continuity checkpoint.
- Merged #290: NVIDIA Super VL transport: 180s bounded per-call timeout, 1500s bounded subprocess, redacted timeout category, no uncertain POST retry; tested offline and recorded as integrated in `3b38b3f411f913736f80cbd9ad402b743c399aca`.
- **Local Qwen 4B evaluation #42711402879 FAILED:** 46 decisions, `9068 > 8192` context overflow, non-conformant 1280×720/60s mostly black H.264, no verified observed revision. Preserve as negative evidence; no more local CPU whole-NLE retries currently.
- PR [#289](https://github.com/ZX7-Labs/Zx7-creative-studio-/pull/289): lossless duplicate native prompt evidence suppression for local adapter. Last observed six of seven CI jobs successful; real MLT editorial job was still running. Not merged at snapshot. This is lower priority under current NVIDIA-first development.
- Draft PR [#288](https://github.com/ZX7-Labs/Zx7-creative-studio-/pull/288) contains a completed failed local model experiment; do not merge its request or rerun by default.

## Active one-shot NVIDIA acceptance

- Synthetic-only NVIDIA Nemotron 3.5 Super VL 120B `nvidia/nemotron-3.5-super-vl-120b-a12b`, source-locked, at most 48 decisions, actual installed editor and hosted function calling.
- Exactly one trial triggered from main commit `76104b4f177ad1eb99e0cb17c8fee194d0d6193e`; [run #42754872382](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/42754872382) was **IN PROGRESS** at snapshot, inside the real native editor/model stage. No verified result yet. **Do not start a duplicate trial**, automatically rerun, or infer a pass before inspecting its exact conclusion, journal, model choices and physical project/media.
- Earlier genuine hosted run [#42669603529](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/42669603529) failed due to 90-second HTTP read timeout after authentic model requests, **not** established API rate limiting.

## What is actually usable vs not yet proven

- [VERIFIED narrow]: Source-integrated native BODY, permissioned editor controls and selected source-pinned Ubuntu install/scripted integration gates.
- [UNVERIFIED]: One complete NVIDIA-generated, creatively meaningful, source-bound, edited-and-revised, conformant project with physical visual/audio observations; independently accepted professional output.
- [KNOWN GAP]: Selected NVIDIA adapter explicitly has no verified original-WAV listening path. A successful visual trial cannot close audio/perception acceptance. Core research breadth is also insufficient for zero-extra-setup worldwide general web.

## Immediate work queue — dependency order

1. Read exact result and artifacts for NVIDIA run #42754872382. Record **first causal failure** or positive evidence with SHA, media profiles, real frame observations, second revision, native project reopen, native source/rights chain. No duplicate paid/cloud run.
2. Fix the identified BODY/native/transport defect **offline first**, with adversarial tests. Never disguise failure by relaxing output, custody, visual/audio or creative quality criteria.
3. Continue provider-neutral BODY tool ABI, real editor controls, meaningful visual/timed/audio review, native saves and realistic benchmark tasks. Separate hosted model competency from a future local model.
4. Reconcile PR #289's final checks; merge/reject only after independent review. Keep docs and project-brain current after every meaningful work block.
5. Launch gate requires technical full acceptance, explicit deployment permission and independent professional artistic evaluation; no public launch claim now.

See [EVIDENCE/INDEX.md](EVIDENCE/INDEX.md), [DECISIONS.md](DECISIONS.md) and [RISKS.md](RISKS.md). Refresh this STATE on the next meaningful result.
