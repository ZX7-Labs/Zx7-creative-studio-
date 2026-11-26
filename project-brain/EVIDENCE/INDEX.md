# ZX7 evidence — retrieval index

Current verdict: [STATE](../STATE.md) and [ledger](../EXECUTION_LEDGER.json). [Complete historical index](https://github.com/ZX7-Labs/Zx7-creative-studio-/blob/766dd9d0076c442f364124b23d1c04412581d184/project-brain/EVIDENCE/INDEX.md) retains all earlier run IDs, hashes, causal reports and positive/negative conclusions at the exact revision.

| Evidence | Original source |
|---|---|
| Earlier full receipts | [Immutable historical index](https://github.com/ZX7-Labs/Zx7-creative-studio-/blob/766dd9d0076c442f364124b23d1c04412581d184/project-brain/EVIDENCE/INDEX.md) |
| Causal failures/retests | [Failure register](FAILURE_REGISTER.md) |
| First inherit inspection | [10 Nov](2026-11-10-INHERIT.md) |
| Wrong-profile, soundless NVIDIA failure | [10 Nov trial](2026-11-10-NVIDIA-ONE-SHOT.md) |
| G0 and F01–F14 fixtures | [G0 coverage](2026-11-12-G0-COVERAGE.md) |
| Perception/held-out comparison | [13 Nov research](2026-11-13-AI-NATIVE-PERCEPTION-RESEARCH.md) |
| Earlier branch inventory | [407 refs](branch-review-20261121.tsv), [459 refs](branch-review-20261125.tsv), [explanation](branch-audit-20261125.md) |
| 472/478 refs, native save custody, failed real models | [26 Nov evidence](2026-11-26-BRANCH-ANCESTRY-AND-NATIVE-SAVE-CUSTODY.md) |
| FFmpeg source failure | [26 Nov FFmpeg](2026-11-26-NATIVE-FFMPEG-GITHUB-403.md) |
| Model truncation recovery | [26 Nov provider](2026-11-26-SUPER-VL-TRUNCATION-RECOVERY.md) |
| Prior 29/29 technical CI | [BODY](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45740635402), [MLT](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45740635652), [Electron](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45740635512), [Chromium](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45740635468) |
| Latest prior test-only regression | [Source gate](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45839052586/job/139975532239), [Omni offline](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45839052518/job/139975531621), [MLT](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45839052536/job/139975531963) |
| Consolidation | [Exact-tip audit and restore workflow](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/workflows/zx7-consolidation-audit.yml), exact successful run/artifact when available |

Add exact SHA/run/job/artifact digest and acceptance tier. Retain negative results; do not treat a source fix or bundle as genuine-model or semantic integration success. Artifacts may expire.

## Consolidation source/recovery receipt

[Exact-tip audit #45862198310](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45862198310), artifact [#15138861698](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45862198310/artifacts/15138861698): ZIP SHA256 `19bb42b5fcac593cc821dda450be46aa583bca921bdc2885ed9397a5b7d85bfb`; bundle SHA256 `09e087440f6225e6c6a83ad7ff25d62a95c4d3d406f3fb8c428ee3e174a5d7b5`. Independent CI restore of every exact remote head plus separate downloaded local Git restore/CRC/fsck passed, 478 refs / 476 distinct tips. Full original Git histories preserved in the bundle; artifact expiry is not permanent retention.

At `56b55a6b44bdabd1311b69514a3f5311497339c6`, locally simulated Git merge for all 478 refs: 150 ancestor, 32 clean identical tree, 70 clean changed tree, 226 conflicts; no actual merge. 1,096 exact object triples, 126 active exact, 385 historical blob already reachable, 585 unmatched. Of these, 221 distinct source and 142 test variants require behavior review. 1,678 non-merge historical patch IDs checked, 91 patch-ID matches in canonical history; five additional noncanonical commits are merges. 722 Python object variants parsed for structural definition leads; AST match does not prove runtime semantics. 35 current Markdown files, 39 historical Markdown paths, 388 path/blob versions, 282 relative links checked with zero broken. Original owner scope documents preserved. Local project-brain 16/16, native controller 150/150 PASS; no paid inference.

Historical Markdown paths no longer in the current tree (preserve original Git history, do not revive as current instructions): `TEMP_ZX7_BODY_NEXT_CHAT_HANDOFF.md` (two old versions), `docs/owner-continuity.md`, `docs/reuse-first-execution-audit-2026-11-07.md`, `research/ZX7_OPEN_SOURCE_FOUNDATION_DECISION_2026-10-29.md`. Archive source restoration and semantic integration are distinct. No old branch is authorized for deletion by this receipt alone.
