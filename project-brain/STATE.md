# ZX7 — current engineering STATE

Checkpoint: **2026-11-10 IST**, exact GitHub main tree reconstructed and verified against the remote tree hash before testing. This file is a snapshot. Refresh current `main`, PRs and Actions runs on entry.

## Integrated verified code

- Repo: https://github.com/ZX7-Labs/Zx7-creative-studio-
- Baseline at this checkpoint: `d76ab91972ce255ee6717f33314d9a68dea62b50` (tree `f669f7bdbffc2188325f81118fcb2ad50cbe9662`).
- #285 source-pinned Electron compatibility, #286 native Ubuntu 24.04 install and scripted create/export/reopen/revise; #287 archive checkpoint; #290 bounded NVIDIA 120B transport (180s per call, 1500s whole trial, no uncertain POST replay); #291 Git-versioned project brain / offline integrity checks.
- **#292 MERGED** at `c41a705...`: the finite NVIDIA provider output-error classification and strict independent native journal auditor now agree. Source/native/controller and MLT editorial checks passed; one unrelated layered-render job was cancelled due CI concurrency and was not counted green.
- **#293 MERGED** [owner delivery gate](https://github.com/ZX7-Labs/Zx7-creative-studio-/pull/293) at `5d78ddd9f91614321c0c470f24e823aac0f237c4`. Its exact-head [real Ubuntu MLT suite](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/42759433152) completed successfully after the previous checkpoint. The integrated [installed original-media BODY job](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/42761207227) also passed. The exact-head [source-and-native-project job](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/42759433093/job/129641383806) was cancelled during FFmpeg setup. The passing model-named PR workflow ran request admission only.
- **Follow-up under review.** Pinned Velorn honored undocumented export aliases that BODY dropped from the readiness request but still forwarded to the writer. The native planner confirmed `codec` and `aspect` could change 640×360 H.264 into 1080×1920 H.265. The follow-up rejects undeclared arguments for owner-profile exports before native calls. Four MCP regression cases reproduced the issue on baseline and pass with the patch. A declared export still dispatches and an unconstrained session retains its native arguments.
- **Local environment limit.** Native editor transport and audit (288 tests), installed runtime and owner workflow (43 tests), and native adapter checks (13 tests) passed. The Debian MLT run did not pass. This image lacks the Cairo blend plugin, and its FFmpeg omitted two requested BT.709 tags. The BT.709 rejection reproduced on unmodified main in both timecode and a physical MLT case. Exact-head Ubuntu CI for the follow-up is the release verification target.
- **Owner export follow-up #296.** Exact-head [Ubuntu source and native project](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/42763872358), [real Electron A/V and installed revision](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/42763872403), and [layered MLT rendering](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/42763872737) passed. [The full MLT editorial run](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/42763872420) was still running when this snapshot was written.

## First video release

**Technical candidate checkpoint: 11 November 2026 at 18:00 IST.** Target the Ubuntu installer and the paired audiovisual test on the pinned editor. **Release decision target: 13 November 2026 at 18:00 IST**, conditional on access to one separately authorized bounded model run and independent creative review. A failed gate yields a no-go and a named blocker. The wider A–L roadmap remains in CAPABILITIES.

| Gate | Status at checkpoint | Required result |
|---|---|---|
| Installed editor, ownership and recovery | PASS on previous Ubuntu fixtures | Clean install, native editable project save/reopen, and original media preserved |
| Paired audiovisual technical proof | PASS on local controller/auditor checks, pending physical Ubuntu CI | Both exports independently verify picture and real nonzero sound. Model interface receives separated frame samples and full-window audio diagnostics for each exact export. A revision occurs between the two. |
| Genuine model, physical delivery and saved editable revision | NOT RUN with new profile | Bounded synthetic run produces two conforming files and an intentional, independently verified picture or sound edit. Reopen and validate the delivered project and source custody. |
| Creative and sound review | NOT RUN | Independent reviewer evaluates pacing, audiovisual coherence, actual listening, and usefulness of the editable result against the brief. |

The proposed `reviewed-av-revision` session profile binds both audio diagnostics and timed frames to the destination and bytes independently decoded for each export. NVIDIA needs separate opt-in for numerical audio data. Its original WAV path stays unavailable in this mode. An offline test for the pinned editor exercises a real title revision with preserved decoded sound. Neither the test nor the new profile starts the old visual-only trial.
- **Open #289** local prompt-evidence dedup, lower priority under founder's NVIDIA-first development instruction; #288 historical failed CPU trial PR, do not rerun by merging its request.

## One authorized NVIDIA live run: FAILED, no retry

[Run #42754872382](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/42754872382) was a **completed failure**, source `76104b4f177ad1eb99e0cb17c8fee194d0d6193e`, model `nvidia/nemotron-3.5-super-vl-120b-a12b`, 48 turn cap, existing credential, synthetic generated neutral footage only. One run only; **do not restart or schedule a duplicate**.

- Verified physical evidence: artifact #13735184585, ZIP SHA-256 `09b2a2cce1d92ecdb12a55458d8b73abe981c70f619210a1ff89e5ee16302e9f`, 22 allowlisted files. All **five** MP4 output paths decode to **1920×1080 / 24fps / 6s H.264 with zero audio streams**; four are identical SHA `1ea56346d0b47f381bc3b5383d5c1a8ae4360ebf93ddd665f788236c15a7777b`, one differs `1b561f6d9fe23a3ff6b6c16d1086b410343a59f2a118cf6e65906bfec64586fc`. **None** meets the owner's synthetic **640×360** delivery brief.
- Genuine model-generated native operations created a source-backed editable project and exports, with one observed verified picture and later native edits, but **no accepted independently verified conformant revised render pair**, no adequate audio listening, no independent artistic approval.
- Root exception: at turn 21 the provider output was rejected as `truncated_tool_decision`, safely recorded with `no_native_dispatch`; the old independent journal auditor incorrectly rejected that legitimate model-error category and aborted after the 48 turns. Corrected by #292 without weakening safety invariants.
- The source-native default MCP delivery preset is `h264_hd` (1080p), not owner project settings; wrong physical output was caused by choosing that default and missing host approval-gate, **not an unexplained renderer transformation**. #293 targets the missing pre-dispatch safeguard.

Local Qwen 4B run #42711402879 was also a **failure** (46 decisions, 9,068 tokens vs 8,192 context, wrong-profile mostly black export); do not spend additional long CPU jobs qualifying this weak candidate while no practical founder local compute exists.

## Immediate next work, in dependency order

1. Complete exact-head Ubuntu CI for the export guard and the paired physical audiovisual fixture.
2. Prepare a separately scoped synthetic brief, exact source, finite model budget, physical delivery checker and artifact policy. The old visual-only request is spent. Obtain explicit consent for a new hosted run and its synthetic frame/audio diagnostic egress before running it.
3. Independently review the delivered editable project and audiovisual work. Expand the accepted workflow to more video briefs and use the same gates for subsequent creative domains.

See [EVIDENCE/2026-11-10-NVIDIA-ONE-SHOT.md](EVIDENCE/2026-11-10-NVIDIA-ONE-SHOT.md), [BRIEF.md](BRIEF.md), [DECISIONS.md](DECISIONS.md) and [RISKS.md](RISKS.md).
