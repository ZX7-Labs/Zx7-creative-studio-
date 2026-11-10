# ZX7 — current engineering STATE

Checkpoint: **2026-11-10 IST**. The #297 candidate source was reconstructed and verified against its remote Git tree. This file is a snapshot. Refresh current `main`, PRs and Actions runs on entry.

## Integrated verified code

- Repo: https://github.com/ZX7-Labs/Zx7-creative-studio-
- Integrated baseline at this checkpoint: `7d1067652b130756d645ea88d2e7844e788e19af` after #296.
- #285 source-pinned Electron compatibility, #286 native Ubuntu 24.04 install and scripted create/export/reopen/revise; #287 archive checkpoint; #290 bounded NVIDIA 120B transport (180s per call, 1500s whole trial, no uncertain POST replay); #291 Git-versioned project brain / offline integrity checks.
- **#292 MERGED** at `c41a705...`: the finite NVIDIA provider output-error classification and strict independent native journal auditor now agree. Source/native/controller and MLT editorial checks passed; one unrelated layered-render job was cancelled due CI concurrency and was not counted green.
- **#293 MERGED** [owner delivery gate](https://github.com/ZX7-Labs/Zx7-creative-studio-/pull/293) at `5d78ddd9f91614321c0c470f24e823aac0f237c4`. Its exact-head [real Ubuntu MLT suite](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/42759433152) completed successfully after the previous checkpoint. The integrated [installed original-media BODY job](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/42761207227) also passed. The exact-head [source-and-native-project job](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/42759433093/job/129641383806) was cancelled during FFmpeg setup. The passing model-named PR workflow ran request admission only.
- **#296 MERGED.** All eight workflows passed on exact head `f480e77`, including [Ubuntu source and native project](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/42763872358), [real Electron A/V](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/42763872403), [layered MLT rendering](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/42763872737) and [full MLT editorial](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/42763872420). Owner-profile exports now reject undeclared aliases before dispatch. Declared options and unconstrained sessions preserve their tested behavior.

## First video release

**Technical candidate checkpoint: 11 November 2026 at 18:00 IST.** Target the Ubuntu installer and the paired audiovisual test on the pinned editor. **Release decision target: 13 November 2026 at 18:00 IST**, conditional on access to one separately authorized bounded model run and independent creative review. A failed gate yields a no-go and a named blocker. The wider A–L roadmap remains in CAPABILITIES.

| Gate | Status at checkpoint | Required result |
|---|---|---|
| Installed editor, ownership and recovery | PASS on previous Ubuntu fixtures | Clean install, native editable project save/reopen, and original media preserved |
| Paired audiovisual technical proof | PASS on the original #297 physical fixture and updated local controller tests. Updated Ubuntu CI pending. | Both exports independently verify picture and real nonzero sound. The model interface receives separated frame samples and full-window audio diagnostics for each exact export. An acknowledged revision separates the observations and comparable decoded media must differ. |
| Genuine model, physical delivery and saved editable revision | NOT RUN with new profile | Bounded synthetic run produces two conforming files and an intentional, independently verified picture or sound edit. Reopen and validate the delivered project and source custody. |
| Creative and sound review | NOT RUN | Independent reviewer evaluates pacing, audiovisual coherence, actual listening, and usefulness of the editable result against the brief. |

The [original #297 physical Ubuntu job](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/42765978704) exercised a real title revision, equal-time changed frames, and a preserved decoded soundtrack. It calls the tools directly. The updated controller and journal auditor use the same reducer to reject container-only changes and compare frames at matching times or PCM over equal sample windows. NVIDIA sessions require audiovisual-mode consent to grant numerical audio diagnostics. Hosted WAV is unavailable. The updated profile and tests run without provider inference.
- **Open #289** local prompt-evidence dedup, lower priority under founder's NVIDIA-first development instruction; #288 historical failed CPU trial PR, do not rerun by merging its request.

## One authorized NVIDIA live run: FAILED, no retry

[Run #42754872382](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/42754872382) was a **completed failure**, source `76104b4f177ad1eb99e0cb17c8fee194d0d6193e`, model `nvidia/nemotron-3.5-super-vl-120b-a12b`, 48 turn cap, existing credential, synthetic generated neutral footage only. One run only; **do not restart or schedule a duplicate**.

- Verified physical evidence: artifact #13735184585, ZIP SHA-256 `09b2a2cce1d92ecdb12a55458d8b73abe981c70f619210a1ff89e5ee16302e9f`, 22 allowlisted files. All **five** MP4 output paths decode to **1920×1080 / 24fps / 6s H.264 with zero audio streams**; four are identical SHA `1ea56346d0b47f381bc3b5383d5c1a8ae4360ebf93ddd665f788236c15a7777b`, one differs `1b561f6d9fe23a3ff6b6c16d1086b410343a59f2a118cf6e65906bfec64586fc`. **None** meets the owner's synthetic **640×360** delivery brief.
- Genuine model-generated native operations created a source-backed editable project and exports, with one observed verified picture and later native edits, but **no accepted independently verified conformant revised render pair**, no adequate audio listening, no independent artistic approval.
- Root exception: at turn 21 the provider output was rejected as `truncated_tool_decision`, safely recorded with `no_native_dispatch`; the old independent journal auditor incorrectly rejected that legitimate model-error category and aborted after the 48 turns. Corrected by #292 without weakening safety invariants.
- The source-native default MCP delivery preset is `h264_hd` (1080p), not owner project settings; wrong physical output was caused by choosing that default and missing host approval-gate, **not an unexplained renderer transformation**. #293 targets the missing pre-dispatch safeguard.

Local Qwen 4B run #42711402879 was also a **failure** (46 decisions, 9,068 tokens vs 8,192 context, wrong-profile mostly black export); do not spend additional long CPU jobs qualifying this weak candidate while no practical founder local compute exists.

## Immediate next work, in dependency order

1. Complete exact-head Ubuntu CI for the updated [#297](https://github.com/ZX7-Labs/Zx7-creative-studio-/pull/297) and integrate it only after successful review and checks.
2. Qualify a separate synthetic-only benchmark before seeking hosted-run consent. Use generated moving footage with a generated soundtrack and an open creative brief. Fix the export window and encoding settings across the pair, then verify both physical profiles at 640×360, 24 fps, six seconds, H.264 with nonzero audio. Independently compare persisted native edit fields and reopen the project. A lossy re-encode can alter decoded samples without a content edit, so require evidence of a saved semantic delta as well.
3. Prepare exact-source, single-run admission and a scoped artifact allowlist for owner review. The prior NVIDIA authorization is spent. Run a new bounded evaluation only with explicit consent for synthetic frames and numerical audio diagnostics. Keep human listening and independent creative review as release gates.

See [EVIDENCE/2026-11-10-NVIDIA-ONE-SHOT.md](EVIDENCE/2026-11-10-NVIDIA-ONE-SHOT.md), [BRIEF.md](BRIEF.md), [DECISIONS.md](DECISIONS.md) and [RISKS.md](RISKS.md).
