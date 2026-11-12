# ZX7 — current engineering STATE

Checkpoint: **2026-11-12 IST**, immediately after native identity integration. **Refresh** `main`, open PRs, CI conclusions, and artifact availability before the next edit. This snapshot is not evidence that later changes passed.

## Current integration and decisive native-video result

- [Main integration commit](https://github.com/ZX7-Labs/Zx7-creative-studio-/commit/4102061b3def7e417ec314ac2ecf8c87a2ea81b9): `4102061b3def7e417ec314ac2ecf8c87a2ea81b9`. The immediately preceding merged [G0 #300](https://github.com/ZX7-Labs/Zx7-creative-studio-/pull/300) preserved the full A–L master plan, T01–T24 and F01–F14 **design and structural regression checks**, not executed artistic fixtures. A–L remains the scope; G0 implementation/semantic coverage is not fully accepted.
- **[G1 native identity #301 MERGED](https://github.com/ZX7-Labs/Zx7-creative-studio-/pull/301)** at `4102061b3def7e417ec314ac2ecf8c87a2ea81b9`, based on exact tested PR head `0222f13db6b762ca5898aca23630ff216f454890`. It connects the pinned Velorn `get_project`, `get_timeline`, and `get_assets` read-only source observations to the host-only identity validator before selected model-authored native edits. It rejects nonexistent/stale clip, track and asset IDs, incomplete/changed observations and exhausted read budgets without native write dispatch or durable write admission. Reads consume the shared session budget. No creative action, original source, editor grant or provider was invented.
- Source identity is based on the real pinned `currentTimelineId`, not a nonexistent `project.id`; source-backed project changes between observations fail closed. Full read grants and clean source attestation are prerequisites; otherwise the identity preflight reports **disabled**, without claiming protected admission. Only the named 20 native routes are covered; catalogs exceeding the 1,000-item source bound refuse complete identity proof.
- **Exact-head CI #301: seven of seven completed successfully** on `0222f13...`: [source/native and 182 universal-core tests](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/43100531028), [installed real Electron A/V, native edit/reopen/revise](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/43100531024), [original custody](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/43100531037), [original-camera discrimination](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/43100531097), [60s physical/native stress](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/43100531038), [MLT original renderer](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/43100530988) and [full MLT editorial suite](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/43100530924), 1,381 executed tests. Tests, installed-model fixture and output checks are **scripted**, not autonomous neural artistry.
- CI artifacts present at refresh: source-custody #13891756186 (1,990 bytes) and 60s physical/editable source #13892886022 (14,914,582 bytes). Artifact existence/CI logs were inspected; their ZIP contents were **not independently downloaded and decoded in this checkpoint**. Do not present artifact listing as a new independent media review. Merge commit has not separately passed the entire video-release test matrix after integration.

## Open blocker and highest-value next dependency

**G1: source-native atomic revision / live human-AI conflict gate.** The new host reader proves object IDs at pre-dispatch, **not** that a human GUI edit cannot land between final read and actual native write. A stale or switched object might therefore be modified after a valid preflight. The next code task is to inspect the pinned Velorn GUI action dispatcher, document revision and native tool write ABI; choose a source-backed compare-and-swap/version guard or equivalent host-owned serialization covering *both* human GUI and AI writes, not merely the host's own asyncio lock. Preserve undo/native source state and reject stale changes without retrying uncertain writes. Avoid a fake host-only revision token.

**Observable exit:** with one real opened installed editable project, an intervening human edit invalidates an AI write at the native commit boundary; zero stale write side effects, no lost human edit, no false write success; fresh AI observation/replan succeeds; controlled save/reopen retains both valid edits, original source hashes, A/V profiles and evidence. Reproduce and measure negative interleavings, restart and direct GUI changes, not only a mocked gateway reader. Scope decisions to video first; do not trade away the open-source/self-hostable runtime.

Other prior proposals #202 and #236 may contain useful designs but are **not merged**; compare against current `main` instead of cherry-picking stale branches. #289 is lower priority under NVIDIA-first development. Do not start a duplicate long local-model trial.

## Video field / release gates

| Gate | State | What remains |
|---|---|---|
| Native installation, editability, rights and scripted physical A/V | **Technical PASS on cited exact heads**, not whole product | Recheck new code after next native CAS change; preserve originals and recovery |
| Native live ID preflight | **INTEGRATED, scoped** #301 | Does not guard a last-millisecond GUI write race or unlisted operations |
| Same-project human + AI revision atomicity | **NOT VERIFIED** | F09 actual GUI/AI conflict, writer-side revision protection and reopen |
| Genuine autonomous neural brief → native edit → A/V observation → targeted revision → distinct conforming export | **NOT ACCEPTED** | New appropriately authorized bounded NVIDIA audiovisual trial *after* offline causal fixes |
| Independent professional picture, temporal sound and artistic review | **NOT RUN** | Human/independent review of actual original output |
| Broad A–L studio and product launch | **NOT READY** | Other fields and release gates remain |

Historical target for first video release decision: **13 November 2026, 18:00 IST**. Without genuine model and artistic gates, the outcome is **NO-GO**, not an automatic launch. No production/public deployment, private owner media upload, uncontrolled paid calls or destructive source operations are authorized.

## Negative evidence and next work instructions

- [One approved NVIDIA run #42754872382](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/42754872382) **FAILED**: real model decisions and source-backed native project, but five export paths were 1920×1080 / 24fps / 6s H.264 with **no audio**, not the 640×360 brief. The controller/auditor mismatch and owner-profile preflight were separately repaired and scripted-tested; no successful new neural rerun. Authorization for that one trial is exhausted.
- [Earlier Qwen local attempt #42711402879](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/42711402879) **FAILED**: context overflow and wrong-profile output. Avoid repeating a weak whole-task CPU evaluation without a reason.
- For current code focused offline regression: `python -m unittest studio_next.test_capability_reference_guard studio_next.test_native_editor_identity -v`; for pinned source read ABI: `node --test engines/velorn/native-identity-source.test.mjs` in the prepared source checkout. Relevant exact-head GitHub runs above already passed; these commands are **next-machine reproduction instructions**, not claims of execution in this checkpoint.
- [RISKS](RISKS.md) owns open R01/R04/R06/R09/R10, [DECISIONS](DECISIONS.md) records D023, and [EVIDENCE/INDEX](EVIDENCE/INDEX.md) retains positive/negative receipts. `docs/continuity/STATUS.md` remains a historical archive, not a second living journal.
