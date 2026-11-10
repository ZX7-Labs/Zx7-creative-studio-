# ZX7 — current engineering STATE

Checkpoint: **2026-11-10 IST**, GitHub source read and evidence artifact inspected. This file is a **snapshot**, not continuously updated telemetry. Always refresh current `main`, PRs and Actions runs on entry.

## Integrated verified code

- Repo: https://github.com/ZX7-Labs/Zx7-creative-studio-
- Baseline at this checkpoint: `5d78ddd9f91614321c0c470f24e823aac0f237c4`. The memory checkpoint merge itself will change `main`; **do not** assume this SHA is always current.
- #285 source-pinned Electron compatibility, #286 native Ubuntu 24.04 install and scripted create/export/reopen/revise; #287 archive checkpoint; #290 bounded NVIDIA 120B transport (180s per call, 1500s whole trial, no uncertain POST replay); #291 Git-versioned project brain / offline integrity checks.
- **#292 MERGED** at `c41a705...`: the finite NVIDIA provider output-error classification and strict independent native journal auditor now agree. Source/native/controller and MLT editorial checks passed; one unrelated layered-render job was cancelled due CI concurrency and was not counted green.
- **#293 MERGED** [owner delivery gate](https://github.com/ZX7-Labs/Zx7-creative-studio-/pull/293) at `5d78ddd9f91614321c0c470f24e823aac0f237c4`: generic optional trusted host delivery profile, native read-only export plan inspection before export, fail-closed no-write wrong dimensions/FPS/codec/duration, trial-only owner profile. No cloud trial triggered. **Verification caveat:** pinned native clients, physical render, original camera, core/source-custody tests passed; latest source-and-native-project CI was cancelled during FFmpeg install and real MLT remained incomplete at merge. Those are NOT green/complete native release acceptance.
- **Open #289** local prompt-evidence dedup, lower priority under founder's NVIDIA-first development instruction; #288 historical failed CPU trial PR, do not rerun by merging its request.

## One authorized NVIDIA live run: FAILED, no retry

[Run #42754872382](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/42754872382) was a **completed failure**, source `76104b4f177ad1eb99e0cb17c8fee194d0d6193e`, model `nvidia/nemotron-3.5-super-vl-120b-a12b`, 48 turn cap, existing credential, synthetic generated neutral footage only. One run only; **do not restart or schedule a duplicate**.

- Verified physical evidence: artifact #13735184585, ZIP SHA-256 `09b2a2cce1d92ecdb12a55458d8b73abe981c70f619210a1ff89e5ee16302e9f`, 22 allowlisted files. All **five** MP4 output paths decode to **1920×1080 / 24fps / 6s H.264 with zero audio streams**; four are identical SHA `1ea56346d0b47f381bc3b5383d5c1a8ae4360ebf93ddd665f788236c15a7777b`, one differs `1b561f6d9fe23a3ff6b6c16d1086b410343a59f2a118cf6e65906bfec64586fc`. **None** meets the owner's synthetic **640×360** delivery brief.
- Genuine model-generated native operations created a source-backed editable project and exports, with one observed verified picture and later native edits, but **no accepted independently verified conformant revised render pair**, no adequate audio listening, no independent artistic approval.
- Root exception: at turn 21 the provider output was rejected as `truncated_tool_decision`, safely recorded with `no_native_dispatch`; the old independent journal auditor incorrectly rejected that legitimate model-error category and aborted after the 48 turns. Corrected by #292 without weakening safety invariants.
- The source-native default MCP delivery preset is `h264_hd` (1080p), not owner project settings; wrong physical output was caused by choosing that default and missing host approval-gate, **not an unexplained renderer transformation**. #293 targets the missing pre-dispatch safeguard.

Local Qwen 4B run #42711402879 was also a **failure** (46 decisions, 9,068 tokens vs 8,192 context, wrong-profile mostly black export); do not spend additional long CPU jobs qualifying this weak candidate while no practical founder local compute exists.

## Immediate next work, in dependency order

1. Review #293 integrated owner-delivery gate against the exact combined `main`; secure profile is private host state, mismatch blocks native write, normal unconstrained exports remain intact. Reconcile the cancelled source-and-native and incomplete MLT checks before any professional release claim; do not rerun the cloud model automatically.
2. Keep the source-native gate's full release-suite verification as an open acceptance item. Use the strong NVIDIA API **only for separately approved, bounded, high-information tests**, never repeated blindly. Original single-run consent has already been consumed. No new NVIDIA run authorized in this checkpoint.
3. Independently audit saved project, timed picture/audio quality, original custody and native editor control depth; close actual errors offline. Future hosted success can prove shared BODY behavior, **not** local model artistic parity.
4. Deliver genuine verified observed-and-revised paired media, professionally acceptable audiovisual creative quality, and remaining A–L capabilities; do not call the system launch-ready until release gates and explicit deployment authorization pass.

See [EVIDENCE/2026-11-10-NVIDIA-ONE-SHOT.md](EVIDENCE/2026-11-10-NVIDIA-ONE-SHOT.md), [BRIEF.md](BRIEF.md), [DECISIONS.md](DECISIONS.md) and [RISKS.md](RISKS.md).
