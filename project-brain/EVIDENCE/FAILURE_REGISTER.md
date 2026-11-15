# ZX7 — forensic failure register (observed ≠ fixed ≠ retested)

This is a **causal retrieval index**, not a reconstructed raw transcript or a second current STATE. Read source-linked [EVIDENCE/INDEX](INDEX.md) and real GitHub job logs/artifacts for full execution detail; original artifacts can expire. Every entry distinguishes actual failure, best-supported cause, **merged corrective source**, and whether a *comparable real model result* independently passed. Source-level green CI is not a genuine-model retest. No credentials/private prompts/media are stored here.

## F-REAL-001 — Qwen local 4B autonomous editor run

- **Original:** [real workflow #42711402879](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/42711402879), failed native job `129481639892`; artifact `13722569378` (unexpired at 2026-11-15 audit, originally scheduled expiration 2026-11-24 UTC). Qwen3.5-4B local HTTP/llama.cpp, real 46-turn native decision trial.
- **Observed:** at decision 46 request rejected with `urllib.error.HTTPError: HTTP Error 400: Bad Request`. Retained trial evidence identifies 9,068 request tokens against configured 8,192-token context, repeated search/describe behavior; decoded 60-second output was wrong-profile (1280×720) and largely black. No conforming reviewed/revised second export.
- **Layer:** model context packing/transport, actual model action selection and owner export conformance—**not proven** a native renderer crash.
- **Follow-up:** [#289](https://github.com/ZX7-Labs/Zx7-creative-studio-/pull/289) reduces duplicate model-facing JSON in failed-turn offline replay from 29,231 to 20,771 bytes. **As of 2026-11-15, PR open/unmerged**, no full-context/tokenizer/quality or real 4B success proven. #288 trial remains an open draft.
- **Root confidence:** specific final 400 and context overflow are supported by job/evidence; a complete post-fix creative root-cause tree is not established. **Status:** FAILED_REAL_MODEL / PROPOSED_OFFLINE_CONTEXT_FIX / NO_SUCCESSFUL_EQUIVALENT_MODEL_RETEST.
- **Do not:** merge all old Qwen candidates or run weak 4B GPU/CPU loops endlessly; first reconcile whether #289 still changes current code and whether a capable authorized model and truthful time budget exist.

## F-REAL-002 — NVIDIA 120B wrong-profile, soundless native outputs

- **Original:** [owner-authorized real synthetic trial #42754872382](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/42754872382), failed job `129626811890`, source `76104b4f177ad1eb99e0cb17c8fee194d0d6193e`, model `nvidia/nemotron-3.5-super-vl-120b-a12b`; artifact `13735184585` (unexpired at audit; original expiry 2026-11-17 UTC).
- **Actual journal:** 112 recorded events, 47 native operations submitted, 40 results and 13 host post-write observations; model output at turn 21 classified `truncated_tool_decision` with **no native dispatch**. Do not infer that unmatched counts represent accepted writes.
- **Independently decoded output:** five saved paths, only **two** distinct SHA-256 digests; actual H.264 1920×1080, 24fps, 6 seconds, **zero audio streams**, against the synthetic owner's 640×360 specification. **Zero** fully accepted compliant audiovisual outputs. Filename containing “640x360” was misleading. [Complete five-path SHA table](2026-11-10-NVIDIA-ONE-SHOT.md).
- **Root cause for wrong dimensions:** pinned Velorn `electron/mcpServer.js` export default `h264_hd`, despite model project settings. This is not spontaneous resizing of a correctly chosen export command. Provider decision auditing separately failed to classify a real rejected provider error type.
- **Follow-up fixes merged:** [#292](https://github.com/ZX7-Labs/Zx7-creative-studio-/pull/292) merged auditable no-dispatch provider error classification; [#293](https://github.com/ZX7-Labs/Zx7-creative-studio-/pull/293) merged optional host read-only export-target/profile refusal; [#298](https://github.com/ZX7-Labs/Zx7-creative-studio-/pull/298) merged physical paired A/V evidence and native source/readback. These are **offline/source/physical correctness checks**, not a successful *paid* neural filmmaker trial.
- **Model trial retest:** NOT PERFORMED after these merges in the available canonical record. Prior specific NVIDIA authorization was consumed; [BRIEF](../BRIEF.md) 2026-11-13 expressly defers paid NVIDIA calls/private media until separately justified and approved.
- **Status:** FAILED_REAL_MODEL / SOURCE_GUARDS_MERGED / EQUIVALENT_NEURAL_AND_ARTISTIC_RETEST_OPEN.

## F-REAL-003 — NVIDIA earlier transport timeout

- **Original:** [#42669603529](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/42669603529); model turn 15 used 87.3 seconds, turn 16 experienced **90.057-second transport timeout**, **no verified export**. No proof of HTTP 429 quota/rate-limiting.
- **Source correction:** [#290](https://github.com/ZX7-Labs/Zx7-creative-studio-/pull/290) merged bounded 180-second per-call timeout and 1500-second outer budget with no automatic retry on uncertain POST. Later real run F-REAL-002 failed on different output/audit conditions, so the earlier 90-second timeout is not a completed creative success.
- **Status:** ORIGINAL_TIMEOUT_CONFIRMED / TIMEOUT_BOUNDS_MERGED / FULL_CREATIVE_MODEL_OUTCOME_FAILED.

## F-CI-004 — combined source Electron scene preflight

- **Original:** [#349 combined workstream #43680525680](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/43680525680), exact code head `11fc1aef2de11b4790e50085039e430dcf39ef6e`. Initial scene installed-editor job failed a version/sandbox preflight **after successful Electron build**; targeted failed-job rerun on identical source head passed actual native scene, save and fresh reopen.
- **Precise first-run cause:** NOT ESTABLISHED; do not call a rerun “proven flaky” without deterministic reproduced predicate.
- **Separate broader outcome:** 19/19 combined exact-head workflow runs eventually successful; [#349](https://github.com/ZX7-Labs/Zx7-creative-studio-/pull/349) merged with same tested Git tree. **Technical native integration passed; independent creative or security test did not run.**
- **Status:** INITIAL_CI_FAIL / SAME_HEAD_RERUN_PASS / CAUSE_UNKNOWN.

## Remaining expensive / acceptance-blocking uncertainties (not mislabeled as past failures)

- **U-G1:** No accepted model-initiated **original picture+audible sound → semantic time-based observation → intentional native revision → two conforming independently reviewed editable exports → true human co-edit**. [R01](../RISKS.md), [G1 build plan](../../docs/BUILD_BLUEPRINT.md).
- **U-PERCEPTION:** [H-PERCEPTION-01](2026-11-13-AI-NATIVE-PERCEPTION-RESEARCH.md) P0/P1/P2/P3 comparative hypothesis has research design but no model-run semantic validation; [#317](https://github.com/ZX7-Labs/Zx7-creative-studio-/pull/317) and [#319](https://github.com/ZX7-Labs/Zx7-creative-studio-/pull/319) are technical transport/sensing foundations only.
- **U-SOUND:** #349 physically proves 5.1 BODY bus and independently source-aware native editor cues, **not** a lossless six-speaker editability roundtrip inside native Velorn, nor genuine sound listening/mixing quality.
- **U-CREATIVE-MEDIUM:** Full safe procedural/code vs native vs hybrid G2 comparison, held-out creative briefs and independent measures remain unrun; no verified advantage for a new CSF.
- **U-RELEASE:** licensed model weights, full A–L professional quality, owner workflow, security/rights, long form/HDR/color and authenticated remote Android are not certified.

## Required exact future failure update

Record `failure_id`, `observed_at`, `head/source SHA`, `job/run/attempt id`, `model identity and context limits` (when any), `media/project/grant version`, `tool request intent`, `native dispatch/ack/no-write/uncertain`, `error chain`, `actual decoded artifact/hash`, `root cause + confidence`, `patch SHA/merge status`, `same-task post-fix retest`, `remaining requirements` and `artifact expires_at`. Link actual complete trace; do not reconstruct missing turns or store private raw media/prompts in public Git. Preserve failure even if fix later passes. Avoid counting multiple CI jobs as independent artistic reviewers.
