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
- **Open #289** local prompt-evidence dedup, lower priority under founder's NVIDIA-first development instruction; #288 historical failed CPU trial PR, do not rerun by merging its request.

## One authorized NVIDIA live run: FAILED, no retry

[Run #42754872382](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/42754872382) was a **completed failure**, source `76104b4f177ad1eb99e0cb17c8fee194d0d6193e`, model `nvidia/nemotron-3.5-super-vl-120b-a12b`, 48 turn cap, existing credential, synthetic generated neutral footage only. One run only; **do not restart or schedule a duplicate**.

- Verified physical evidence: artifact #13735184585, ZIP SHA-256 `09b2a2cce1d92ecdb12a55458d8b73abe981c70f619210a1ff89e5ee16302e9f`, 22 allowlisted files. All **five** MP4 output paths decode to **1920×1080 / 24fps / 6s H.264 with zero audio streams**; four are identical SHA `1ea56346d0b47f381bc3b5383d5c1a8ae4360ebf93ddd665f788236c15a7777b`, one differs `1b561f6d9fe23a3ff6b6c16d1086b410343a59f2a118cf6e65906bfec64586fc`. **None** meets the owner's synthetic **640×360** delivery brief.
- Genuine model-generated native operations created a source-backed editable project and exports, with one observed verified picture and later native edits, but **no accepted independently verified conformant revised render pair**, no adequate audio listening, no independent artistic approval.
- Root exception: at turn 21 the provider output was rejected as `truncated_tool_decision`, safely recorded with `no_native_dispatch`; the old independent journal auditor incorrectly rejected that legitimate model-error category and aborted after the 48 turns. Corrected by #292 without weakening safety invariants.
- The source-native default MCP delivery preset is `h264_hd` (1080p), not owner project settings; wrong physical output was caused by choosing that default and missing host approval-gate, **not an unexplained renderer transformation**. #293 targets the missing pre-dispatch safeguard.

Local Qwen 4B run #42711402879 was also a **failure** (46 decisions, 9,068 tokens vs 8,192 context, wrong-profile mostly black export); do not spend additional long CPU jobs qualifying this weak candidate while no practical founder local compute exists.

## Immediate next work, in dependency order

1. Verify and review the export-argument follow-up on exact-head Ubuntu CI. The new regression must preserve zero native calls for undeclared options and normal dispatch for declared options. Reconcile the cancelled source gate before a professional release claim.
2. Keep the source-native gate's full release-suite verification as an open acceptance item. Use the strong NVIDIA API **only for separately approved, bounded, high-information tests**, never repeated blindly. Original single-run consent has already been consumed. No new NVIDIA run authorized in this checkpoint.
3. Independently audit saved project, timed picture/audio quality, original custody and native editor control depth; close actual errors offline. Future hosted success can prove shared BODY behavior, **not** local model artistic parity.
4. Deliver genuine verified observed-and-revised paired media, professionally acceptable audiovisual creative quality, and remaining A–L capabilities; do not call the system launch-ready until release gates and explicit deployment authorization pass.

See [EVIDENCE/2026-11-10-NVIDIA-ONE-SHOT.md](EVIDENCE/2026-11-10-NVIDIA-ONE-SHOT.md), [BRIEF.md](BRIEF.md), [DECISIONS.md](DECISIONS.md) and [RISKS.md](RISKS.md).
