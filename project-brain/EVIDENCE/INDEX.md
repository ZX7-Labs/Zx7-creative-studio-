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

Permanent Git archive receipt: [archive run #45863302941](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45863302941), all three jobs PASS, independently fetched tag at `cb3121df28ec12da391dac42a4485c3c1bb83213` and restored exactly 478 refs in a fresh bare repository ([independent job](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45863302941/job/140060445380)). [Full archive inventory](https://github.com/ZX7-Labs/Zx7-creative-studio-/tree/cb3121df28ec12da391dac42a4485c3c1bb83213) retains original tip names and exact object variants. This is an archival tag, not a product merge; branch retirement remains unapproved. Latest tag snapshot has 389 Markdown path/blob versions, 125 exact active variants, 386 historically reachable and 585 unmatched; 221 source and 142 regression-test variants remain for semantic review.

## Whole-studio reconciliation and historical native admission restoration

- Live comparison of all 478 refs against the verified archive: only the canonical workstream advanced at observation. The archive has 1,096 object triples; 585 unmatched, including 221 source and 142 test variants. Local reverse-patch and three-way checks found structural equivalence for 13 source and 5 test variants. Do not infer semantic closure.
- Historical native catalog guard at `d6fffb40bb218f93dab9b3f5191666e82f1f0e0d`: its 8 original tests against the current source produced 8 failed assertions across 3 tests. Reused the historical validator, catalog checks and regression tests, sharing validation with the gateway, in [dbc6257b](https://github.com/ZX7-Labs/Zx7-creative-studio-/commit/dbc6257bfee830cb8e78a40732d04cd139f7863f). Focused local suite: 32 passed, 33 environment-dependent skips, zero failures. Other local checks: discovery/gateway 88/88; visual/research 62 passed, 3 skipped; long physical suite timed out, not passed. Exact-head CI is separate.
- [Unified installed artifact #15139402602](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45863681059): independently downloaded ZIP SHA-256 `f4e6d724888f8f69e6fbfc7a1bace7f690472615c507862eccfa7fc6df090ca2`; 16/16 manifest entries verified for size and hash; four MP4 files fully decoded. Editable graphics/visual graph, Blender source, project revisions and relocation are technical evidence; the manifest explicitly excludes genuine model/professional acceptance.
- Local formatting audit at `b124d560e0920c76b3cc0d9c4d6cc1543d8ba28f`: 35 Markdown files, 278 relative links, no broken links, unclosed fences, malformed ATX headings or leading tab indentation outside fences. Scope correction is a subsequent revision; its checks are separate.

Additional historical checks: Crossref malformed-year regression and complete/partial versioned MCP catalog regressions replayed on current local code, 3/3 PASS without changes. Direct server's previous JSON Schema validator accepted an undeclared `fakePermission` parameter; restored shared `native_admission_validator` rejects it and retains nested native schema flexibility. Reused it in direct MCP server and restored two original SDK tests from `d6fffb40`. Combined local catalog/MCP/gateway/fabric suite: 64 passed, 35 skipped (optional SDK absent), zero failed. Direct SDK dispatch proof requires installed CI. Exact tested blobs `d31091b83572685736ec75683247dbdf7b72e97a`, `b2b0b900211cced840e23a8db0a1d49c9277d413`. At `a59e2486`, checked all 11 changed Markdown files, 127 relative links, zero formatting/link errors and exact STATE/ledger binding. Earlier CI: `f7492f05` 28 success/1 cancelled; `dbc6257b` 19 success/7 cancelled/3 running at observation; new commits restart concurrent CI. No full acceptance.

## Source-pinned admission compatibility correction

At `458ace268dda80cdbecd00c77829d997c5db3492` installed CI exposed actual regressions from previous historical guard restoration. [Source gate](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45866754019/job/140071449377) rejects the unconstrained native codec alias; [loss-aware actual editor](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45866754225/job/140073419050) and [unified creative handoff](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45866753793/job/140072025956) reject the gateway-injected `__zx7ExpectedRevision` on source-attested asset placement. Underlying source owner: native_editor_identity.py and body_editor_mcp.py. Reuse exact fenced operation source policy and commit predicate at both boundaries; only strip the private value for schema validation, forward unchanged on the actual source commit; keep read-only preview free of the private field. The upstream pinned resolver explicitly recognizes codec/aspect/preset/size aliases; allow those only in the source-verified unscoped open export schema, pass the same aliases to readiness and retain closed owner delivery. Unknown fields and spoofed tokens remain rejected. Local 302 tests ran, 267 passed, 35 optional SDK skips, zero failures; actual SDK and native installed verification not inferred. No neural trial or feature expansion. Exact tested blob IDs are in ledger.


### Installed SDK and physical fixture follow-up

At `fbdbfc3ce92dc042a15bec99cac2914a2c357ade`, [source gate #45869371030](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45869371030) passed all four jobs; [source/native job](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45869371030/job/140080472022) records 336 official MCP SDK tests OK. [Unified installed creative gate](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45869370859) and [Project Brain](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45869370774) passed. Actual native editor [run](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45869371013) fails in common E2E line 528 because a missing-asset negative request omits required native revision and returns no placement-plan metadata; [atomic range](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45869371111/job/140081143019) exhibits the same traceback. Local fixture blob `1a98b443368dd6e5719a9ffe21ec02ee186fae2e` compiles; it separately tests tokenless rejection/no mutation, then supplies the live source revision to existing invalid-asset negative cases. Production source unchanged in this fixture correction. No physical retest pass claimed yet. Exact-head observed counts: {"success":17,"in_progress":3,"failure":9}. No model or professional acceptance inferred.

## Whole-studio discovery and archival correctness reconciliation

Preceding exact source `faa0164724f0e89543f0e0bf9a8b8c9255166f9b` observed workflow counts {"success":28,"in_progress":1}. [Native Electron](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45870260347), [source gate](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45870260362), [continuity](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45870259833), [unified creative](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45870259932) and [installed release proof](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45870260276) passed; genuine local and hosted jobs skipped (140083604936, 140083534559). Tested merge `7ae3747e800dfb9b830fd078627db70d80d7f7c7` and source have same Git tree `3e50bef8f8c02d987dbaa5f118d5f4515153f55a`. Installed artifact #15143422540 ZIP SHA-256 `8849f64710815d87975175ab2b3d7d1d15a84114d8d24ee792133038094c39e3`; independently CRC/hash verified 24 files, fully decoded three movies, checked both SQLite databases, and read raw 1,743-test result (1,713 passed, 30 skipped). Unified #15142442764 SHA-256 `5fb10712b0915be50439562a5c9f56894f153bbc83cb9ab6c2024df889296b4d`, 16 manifest files and four full MP4 decodes; original/revised/relocated editable sources, no genuine neural or independent artistic acceptance.

Historical [e3f8b057](https://github.com/ZX7-Labs/Zx7-creative-studio-/tree/e3f8b057cf45eae767dce0433388fc8deac09f07) fixes bounded native search vocabulary beyond 128-char display summary; old regression reproduced RED (wrong marker selection instead of asset placement). Reused exact historical behavior in existing CapabilityFabric; additionally bound vocabulary in live gateway revalidation and isolated returned requires/may_enable lists. Old [1b74a4ea](https://github.com/ZX7-Labs/Zx7-creative-studio-/tree/1b74a4ea) registry used an atomic refresh lock; reuse the actual gateway instead of introducing another registry. Deterministic overlapping discovery reproduced stale-publication race, failed refresh preservation already passed. Four initial discovery/refresh regression failures, one existing passing test; after repair 80/80 local tests. Current source comparisons show stronger existing motion exclusive publication/physical decode/fsync, reference sample-count energy and identical reference guard; old audio gain, clip grade, empty track fields exist and director gap color is correctly a render argument, not redundant plan field. Exact archived variant IDs/dispositions in typed ledger.

Actual Python 3.13 ResourceWarnings led to targeted reproduction: archive and job-status raw SQLite context managers left handles open, and a workspace with URI-reserved chars could copy an empty wrong DB. Three new local regressions RED (two assertion failures/one missing table error); close with contextlib and encode exact absolute file URI; 26/26 archive/service tests PASS. Additional existing cross-domain 156 run/153 pass/3 SDK skips and physical selected 37/37 pass. No unique-count summation across suites; no local SDK/Blender/MLT full gate claim. Exact tested code blob IDs stored in ledger. No paid inference, branch deletion, new product framework or independent artistic claim.

## Exact-head technical closure of shared discovery and SQLite reconciliation

Source `13482c55b7f084910beca6c8413953d6d60f4b70` completed 29/29 successful PR workflows; prior `faa01647` ended 28 success/1 cancelled. Synthetic PR merge `0d368a18376f2265f9687008b8ce1be256dd609e` and source have identical Git tree `1619ecf7c133a7a3e70a43f2e89b24dd1665b575` (Git commit objects inspected). Actual hosted/local model jobs 140093337739 and 140094132646 skipped. [Installed raw log](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45873124419/job/140093334903) reports 1,751 tests, 1,721 passed, 30 skipped, zero failures. [Independent CI re-download and integrity](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45873124419/job/140099416931) verified published artifact #15144482504 SHA-256 `6cadb71296c77d6dabd1513c6b3db99d5da425f92dc90786acba37a7b91f08e1`, 24 files and 5 source-bound publication receipts; artistic quality false. [Full MLT log](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45873124498/job/140093462898) reports 1,751 tests, 1,750 pass, 1 skip, zero failures. [Source gate](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45873124446/job/140093336314) includes 336 SDK tests. [Unified installed gate](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45873124339/job/140093772503) passed; artifact #15144151611 published SHA-256 `649289cb7ca2e2579250b4171f85e96a2952caa192e5ac11f21a6439f061f408`. This checkpoint inspected actual CI logs, Git objects and artifact metadata, not a new independent local ZIP decode; keep preceding local audit distinct. No model or professional acceptance, branch retirement or feature expansion inferred.

Additional archive reconciliation against `13482c55`: historical asset-reader blob `dc1c23cc2dab9e471a5d10e9996a7281938c3866` equals current `4c5ac4536d06198c371c6d73c190f5557a58a34b` outside the strictly stronger transport-status block. Historical BODY affordances blob `e88ba436094f1d56696224d0b35ea3bfc366937e` equals current `8b0fbb06efc31f4f550491602370be80faeb7b91` after exact permission/runner-admission changes. Ordered full-file comparisons verified; existing four targeted regression tests in [installed log](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45873124419/job/140093334903) pass. No new test execution or source changes. Old timeline identity source is absent at its historical path; current native identity owner is stronger in live state/revision custody but old reference-coverage equivalence remains unclassified. Correction: [642565f1](https://github.com/ZX7-Labs/Zx7-creative-studio-/commit/642565f1252f10caf65a1aa6f434672d25dcc3ba) is the post-render clock-only autosave delivery correction; its exact distinctive code and regression already exist in the active source. It is not evidence of a pending marker-admission fix. Do not replay it; find exact marker source or reproduce before editing. No branch retirement or full behavior closure claimed.

## Archived timeline identity: source-attested explicit reference coverage candidate

Reviewed old timeline identity source/test variants against the current host-owned native reader and generic guard; do not revive the old module. Pinned [Electron schemas](https://github.com/VelornLabs/velorn/blob/b3c02adbd5c0779feb8abf34978299e9502cc0e7/electron/mcpServer.js) and [renderer dip target resolution](https://github.com/VelornLabs/velorn/blob/b3c02adbd5c0779feb8abf34978299e9502cc0e7/src/services/mcpActions.js) establish explicit clip/track fields on existing host-grantable operations. Baseline `caa5071dcb07f3165b2e2056ad64db079add53b3` omitted 28 source-attested reference paths; candidate source blob `6cfbd7b3412ea584ed7004393cf287f1679ffc23` covers all 28 (structural mapping comparison, not runtime RED/GREEN). Candidate test blob `af4ca64c2de8fa51319111d70a54bdcdc382ff6c` adds positive/negative path checks and a gateway mixed-label-batch no-dispatch regression plus valid explicit/filter calls. The native label resolver can return matched IDs alongside missing IDs; host must not silently approve an incomplete explicit target list. No new grants or last-mile CAS claims. Existing provider and professional acceptance unchanged. Runtime tests and exact-head CI pending; marker/effect/cue-specific inventory coverage is separate.

## Exact-source native reference coverage completed; marker candidate follows

Source `134ea090d8c293b1c9867de219a8ad32c8d5cbad`, tested merge `e00afafc2a450329771fbc452280ccbbc4f06913`, identical tree `0fe910ad409916ed5190b0ffd8f363cc3f69c954`: **29/29 workflows success**. [Core](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45879882839/job/140116242464) 230 run / 226 pass / 4 skip; both new reference regressions pass. [Native source gate](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45879882839) four jobs pass. [Installed](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45879882526/job/140116240531) 1753 run / 1723 pass / 30 skip. [Independent download](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45879882526/job/140124474029) validates matching ZIP SHA256 `6d20464e408caec7773288de1a5fafb2d97ae252b3263e9b300e941b39d7617a`, 24 files and 5 publication receipts. [MLT](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45879882833/job/140116348153) 1753 run / 1752 pass / 1 skip. Unified artifact 15147335161 has published digest `513d15459a1e612ba7ea086d458f38cff703d479146f78bd737b1f8592ea0d53`. Genuine hosted/local model jobs skipped. Mobile first attempt apt HTTP 403, [targeted retry](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45879882820) success. New ZIPs not independently decoded locally.

Parallel ordered source comparisons preserve eleven archived variants without replaying old implementations; typed ledger names every variant and exact blob. The next marker candidate `c7ebb91fa581765fc1dd46daa4fb871101947ee2` fixes host explicit-ID admission based on actual pinned snapshot marker array/count and native resolver; two Python regressions and one Node ABI characterization added. Runtime verification pending, no native last-mile race/CAS claim. Existing source-pin and permission boundary unchanged. No acceptance promotion.

## 27 November — verified marker baseline and owner-approved execution refinement

Exact `5b9efc497717f81e63c26c14ff621af58201bc57`, tested merge `cc11df9ea3e070d7d64cf4c7dc9e9c0ab4565d8d`, equal tree `fadccded3cd51b8641bd074159e0d0127fb8741a`: 29/29 workflows success. [Core](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45889714101/job/140149056131) 232 run / 228 pass / 4 skip; [native source](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45889714101/job/140149056088) 258 Python and 42 Node pass including all marker regressions. [Installed](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45889714441/job/140149056589) 1755 run / 1725 pass / 30 skip; independent download job 140156764253 matched artifact 15152416041 SHA256 `9a955efceda8c5c949d1b86354a96e464434db632ad5730a82a0c8ffd2d3d946`, 24 manifest files, five receipts. [MLT](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45889714235/job/140149056186) 1755 run / 1754 pass / 1 skip. [Unified](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45889714245) artifact 15151735553 digest `604b5d78b39631b069a26ed541927e9c187dd6432ff27de5263e393efa3dd19f`. Latest ZIPs not locally re-decoded in this review. Hosted/local actual model jobs 140149059289/140149407365 skipped. No marker CAS, neural art or independent professional acceptance implied.

[Independent engineering assessment](2026-11-27-ENGINEERING-STRATEGY-ASSESSMENT.md): owner accepted outcome-first execution; preserve original scope and authority, change practical task ordering. No runtime change in documentation commit; preserve previous evidence and failures.

## Critical path — 27 November, one source-bound A/V review instead of two

Baseline `c02c2d0b6989eed4b0a9e7232ba79c2e18012221` (docs integrity [passed](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45893690742)). Existing `zx7_observe_verified_export_av_window` produced frames and timed PCM, but strict pair gate ignored the combined evidence. Matched synthetic controller/auditor regression RED: separate route completes; combined full-duration route exhausts budget. Candidate GREEN: both admit the same technical pair, 10 → 8 scripted decisions and 9 → 7 calls; partial coverage, overstated PCM duration and tampered receipt fail. No new tool, grant, artistic choice, semantic listening or professional acceptance. Exact local source/test blobs in ledger; 201 eligible affected tests pass. Broader local runs could not execute three SDK-dependent cases and two repo-script cases because installed wheel environment lacks those dependencies. Added physical MCP decoder parity regression remains pending CI. This is not measured neural latency or successful genuine model trial. Next: exact-source CI then consent-bounded model qualification/comparable synthetic trial; no acceptance promotion.

## Critical path — 27 November, source-bound delivery readiness

Parent `385534021c47efdecf70685e5f54095ea37e3d2d` passes 29/29 technical workflows (actual neural jobs skipped). [Revision](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45932518731), [Omni offline](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45932518469), [source with targeted unchanged-source apt retry](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45932518613), [MLT](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45932518748), [installed](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45932518653). Installed artifact #15169717251 SHA256 `4130f18bdbda3cbf91262384a144e4f6360394983e1625f978756e0bfcc62f87`; CRC, 24 manifest entries, exact installed controller/test blobs and full FFmpeg decode of all three films independently verified. 1,757 tests run / 1,727 pass / 30 skip. Prior failure/fixture recovery details [PR receipt](https://github.com/ZX7-Labs/Zx7-creative-studio-/pull/356#issuecomment-7208810798).

Actual retained failed Super VL journal artifact #15078171115 CRC and SHA256 match the earlier record. 12 searches in 37 decision turns, two native stale refusals, save at 31 then search at 32, zero exports. New host readiness frontier offers only existing granted save/export/verify choices; no action dispatched automatically or source-capture requirement removed. RED on exact baseline: four-turn fixture has save and render but no verify; GREEN: same three chosen actions require 3 rather than 6 decisions, same native-call sequence, missing/empty state and malformed capture/grant/invalidation negatives pass. Affected suite 223 run/217 pass/6 environment import errors (MCP and repository-only scripts), zero assertions failed; exact controller and test Git blobs in ledger. Candidate CI pending; no actual model rerun, professional quality or verified neural efficiency claim.

## 27 November — genuine indexed failure and controlled next arm; archived scope reuse

Exact `fce6049bbee21ad65a3421e383a862644d1aa364` passed all 29 technical workflows. [Indexed real run #45934918405](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45934918405), artifact #15171390542, ZIP SHA256 `c1f880a29113a4ffa967deebf66a7fa7544f51b7110986bdb5fec2f510ddde86`, CRC pass. 117 events/48 turns, 17 searches, 589619 reported tokens/212272 search tokens, 1026490.065ms model vs 1925.473ms native MCP. First cut SHA `fe0eaf543c1d558412ed7bb51c8a7fa11268b0d08b5ebf3372600fbccb540d78`, independent full decoder + probe 640x360 H264 24/1 144 frames 6s AAC; saved project hash and original bytes match retained receipts. Model sampled frames 34 and numeric audio 35, text revision 41, save 47; second export absent. Failed budget gate, no inferred semantic hearing or professional quality. No actual rendered-original source pixel proof. Prior trigger revoked. Previous journal search count corrected to 14 per PR comment #7209100544.

Same-source direct vs indexed whole-interface comparison: [#45937037913](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45937037913), exact one-use child `e4abbd93c6aa82a3593e1014dd069fac05d68f23`, revoked by `9d27019f0a8b2e0aecd29ad954cc4cbc51322807` restoring parent tree. Only existing catalog mode differs; preflight before credential, identical synthetic policy/48-turn cap. Result pending; not a G2 full A/B/C acceptance or repeated statistically controlled experiment.

Independent parallel reuse: exact candidate blobs from `cea19dadc38cccb212e9d37331ca1869d200b724` and `633348babde51ba037bf1917fe1f051bd2515aae`; source parents matched live current blobs. Research RED explicit provider unsupported, GREEN bounded three new metadata sources, path/rights/network refusals; scheduler RED mislabel queued/running jobs as physical execution, GREEN durable state only. Actual 63 affected tests, 58 pass/4 missing MCP skips/1 no-display error; targeted real Xvfb desktop passes (59 distinct passed). Exact seven local Python blob hashes matched candidate. Real public APIs and SDK verification pending new CI. No A–L professional gate promoted.

- 27 Nov, live research/physical oracle: [research failure](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45937275501) on `02d519e863615efef59966eee56e9fa60758665e`: Cleveland passed, NASA real Apollo IDs with spaces rejected (three independently fetched records), Europe PMC same query returned valid JSON independently but failed on runner; exact runner cause open. NASA RED fixture → GREEN bounded segment encoding; 71 affected tests/67 pass/4 SDK skips, final FFmpeg-only frame tests 7/7. Four aligned/offset/sound-only/picture-only synthetic cases compare uniform vs known targeted sampling; physical receipt only, not blinded model acceptance. [Installed collaboration job](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45937275794/job/140303602801) blocked at apt HTTP 403 before tests. Source blobs `5dde50ab25f64d4c6ec3e710249d8f4cd3fa3be0`, `bacceff8cbddd19eb32e50f3c70a354049259e9b`, `830e5f425614439b02f8ebfc540f48212211274a` match local tested source. New exact-head CI required.

## 27 November — direct comparison terminal failure and source-custody repair

[Direct run #45937037913](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45937037913), artifact #15171327555 ZIP SHA256 `438d92a0b030ace86723a61aafc03b8cf91618d80207eb2e283601e8fcd0c684`, CRC verified. 135 events/48 turns, 0 searches, 1,315,967 reported tokens (1,251,098 prompt/64,869 completion), model 578,863.636ms, native MCP 3,390.493ms, 14 write ACKs, 2 verifications. Two 640x360 H264 24fps 144-frame six-second audible exports: `9da3574b0244e54cfbc9131d3f61482f2a132e7106a93721b22f49c411f8afbd` and `31391ea2abd493e461b3d597cb97c611b9dbe9e89c00c3a04d34c08bed3c8cd7`. Independent full FFmpeg decode: 79/144 RGB frames changed, mean absolute RGB difference 0.848704/255, identical decoded PCM SHA256 `4762b126e870a82caa75aa4549f5903f2a46b507a4d06f1f0a0e637aa0ececa1`, RMS 0.05555946. Render-time project SHA256 `29d6785bd0dee6e0c3288a4730f555b1734190e596a79cf65b121d0007b9b893` and `8ff5dc05b4bcae9256b87d98825606a6c0afbdefe63820fb6b37a5e97b600561` match actual retained autosave files. Actual source-bound A/V pair comparator accepts prefix through seq 118 / turn 41, revokes at seq 120 / turn 42 after model-selected text edit; final two export requests rejected output_exists. Final evaluation FAIL turn_budget_exhausted; no auto replay, finished current delivery, semantic hearing, rendered-original pixel proof or independent artistic approval. Indexed vs direct uses same original runtime/model/brief, but only one trial per arm; direct 2.23x provider-reported tokens and shorter reported wall time, no general architecture ranking. Duplicate last-receipt projection experiment on 111 controller fixture contexts saved only 2.31% serialized bytes, not provider tokens; not implemented.

Research: [live #45937892821](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45937892821) initially failed Europe PMC despite 30/30 offline research tests and three actual NASA leads. [Anonymous runner diagnostic #45938105014](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45938105014) exact query HTTP 200/20,839 bytes/3 parser-accepted records/2.733s, control p53 timed out. Single unchanged-source targeted retry SUCCESS, diagnostic trigger retired forward at `dd8ab3f4ba336e67cac56bd82b4984100f5d8d11`.

Source custody: on exact parent `4e2c4338841e77f601443cfc55f986c53437b183`, generated local HLS playlist referencing separate MPEG-TS segment accepted as MP4, MP3 and FLAC immutable media; timeline and delivery probe also accepted. Five independent RED assertions. Fix adds self-contained movie demuxer and local protocol restrictions to probe and actual decode, with matching compressed audio demuxers; genuine MP4/MOV/MKV/WebM/MP3/FLAC and extensionless CAS checks pass. 82/82 affected tests on exact candidate blobs; no new dependency, no broadened scope, not an OS sandbox or universal decoder proof. Historical detailed archive review preserved under exact parent ledger link rather than growing mutable ledger past 80KB.

- 27 Nov follow-up: exact decision budget was absent from the Brain's turn context, although the genuine direct run formed a reviewed pair then continued at turn 42 with six decisions remaining. RED KeyError → GREEN current required evidence flag and exact max/remaining turns. Model-selected extra edit remains permitted and revokes current evidence; subsequent verification restores finish, no artistic approval. 215 controller/audit/provider tests run, 210 pass, 5 local import errors (MCP and repo scripts), zero assertion failures. No new provider run.
- Actual authorized reference root escape: in-root HLS points to synthetic TS outside root; prior reader decoded it. RED → GREEN existing shared video-input policy at all three reference decoder entry points; six physical tests passed. Not a full sandbox claim.
- [Repeated live Europe PMC timeout #45938988502](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45938988502/job/140308669885) retained. After prior runner diagnostic and successful unchanged-source rerun, implement one exact same-URL timeout-only recovery for that approved anonymous metadata GET. Tests cover direct/wrapped timeout, second timeout terminal, no retry on HTTP denial, redirect, invalid JSON or unrelated provider. Research suite 31 run/27 pass/4 missing-MCP skips. Exact local candidate blobs match; live provider validation pending. Parent CI observation {"in_progress":15,"success":13,"failure":1}.

- 2026-11-27 staged original-source custody: exact baseline `ec4af1176fc9cd91d18b5e0dd7ef1051b6784f9a`; local deterministic post-validation same-size SVG replacement RED incorrectly attested replacement bytes; GREEN validated staged original survives and invalid replacement remains unattested. Combined regression 92 run, 88 pass, 4 SDK skips, zero failures. Exact source/test blobs `4a882a8205fc9911e2de8bb8ca51e552e46448f4`, `efaf60371e81203ca93758566e4990f348f1f3d9`. No OS sandbox or independent creative acceptance claim; hosted gates pending.

## 27 November — genuine isolated perception and bounded retrieval

[Super VL visual #45941783748](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45941783748), source `95eb692104bc88d042f7203a90ea6b9121b6f4f6`, artifact #15173003314, SHA256 `fa09a74be694c973e9b55e4f3c7aa85970adc5e1203c0fa422e2735b13ac28df`: 5/5 typed answers correct, 15,047 reported tokens, 29.442s model wall. Independent CRC, five full film decodes, all 15 PNG hashes/RGB comparison and numeric sound bins verified. Only basic sampled visual and numeric timing competence. One-use trigger retired `eea64016d32165400a576a5dacea88f0ef706891`.

[Omni raw WAV #45942171828](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45942171828), source `aa8c21526f6f12dab636f61ef5becfb59b3fd5db`, artifact #15173153626, SHA256 `8c1540adbf8787325ac077d1c3c9d1d29fed8aed7d19b09e4b1f4b49524144c6`: 47 preflight tests pass, genuine model FAIL 1/4; all four reports rising, one invents high pitch on silence. Four source MP4 SHA/CRC/full decodes and WAV SHA verified; independent 16k mono PCM byte-identical, FFT 880/440, 0/0, 440/880, 440/440. 4,351 reported tokens, 4.375s model wall. No proven raw listening or professional quality; one four-case calibration does not localize provider internal cause. Trigger retired `e0fc18741813bccd12ac1daab9e16006e226adce`.

Exact parent `21bac3469fe6d87c630fd66178f5c17796b3810e` 28/29 workflows successful; Europe PMC [live #45939750087](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45939750087) persistent timeout after bounded retry. Prior 17-search trace had 101 returned IDs/23 distinct. Small complete exact-ID retrieval index (48 operations, 4096 bytes, no grants), large catalog unchanged. Local RED/GREEN, 250 affected tests run: 243 pass/7 environment import errors/zero assertion failures. Exact source/test blobs in ledger. No genuine efficiency claim or acceptance promotion.

## 27 November — speech discrimination, exact installed baseline and compositional measurement

[Installed #45942606959](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45942606959), ZIP #15174550542 SHA256 `47d53ab4716c683965ba41832323d8a9815234097facb64d53b0c9851788e788`: CRC and 24 manifest entries match, merge `10afc0a827195f3d7e5d3ae90a3d271af1ee87a4` exact same tree as `d48af496fa70a9208a94016fd5e4d7320d05d0e1`, 1775 run/1745 pass/30 skip. Current technical checks {"success":28,"in_progress":1}. [Cross-process initial failure](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45942607052/job/140320939079) is native commit-boundary refusal, targeted same-source retry passed; root cause not proven. No guard relaxed.

[Omni speech #45944055906](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45944055906), artifact #15174256003 SHA256 `a71c16e0191a302d53ff091b8a154bb3f27b8b09786fea99a3362d32af6c2352`: exact source `b282fd85606c38b87be2411833f092fe628da6a3`, retired trigger `b0afff228fbf84f32a18e03252ec3bec59ee75e5`; 4/4 short synthetic English speech/silence reports matched, 3785 reported tokens, 5219.613ms model wall. Four MP4 full decodes, 16k mono 40000-sample WAV and independent PCM hashes match; silence RMS 0. Pitch FAIL 1/4 remains. No general audio artistry inference.

Exact installed parent reconstructed; candidate four targeted RED tests 2 failures/3 errors: mutable adapter context corrupted persisted owner facts, missing durable model/dispatch measurements, full 77-tool grant profile returned no exact index. GREEN 74/74 affected tests from exact wheel with candidate four blobs, actual fixture render/decode, unchanged grants. Model-facing snapshot copy; intent+measurement persistence; bounded reported usage, failed call retains elapsed not stale usage; known/legacy pending resumes without re-inference. Complete or absent identity lookup cap 96, existing 4KB/160-byte bounds preserved. New source/test blobs in ledger; no actual model cost or quality comparison claim yet.

Exact installed [#45945182492](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45945182492), source `3320ba88cee133f26947098ce34f775a36657329`, tested merge `5457fd39482f8266bfb366bbf1443bf4853bc871` same tree; artifact #15174368688 SHA256 `aa657722d44cf725d9539ea4b0699f67c0a72f7a7b776dc6e57905722cb999ac`, local ZIP CRC, 24 manifest entries, wheel source blob equality; 1778 run/1748 pass/30 skip/zero failures. Independent full decode: 57-frame 320x480 mixed 4.75s with AAC stereo 48k, 33-frame 320x480 2D 2.75s with AAC stereo 48k, 24-frame 256x256 3D 2s video-only. Separate CI receipt job #140332574217. Parent 28 successful workflows, MLT #45945182260 running. Genuine indexed #45945314825 step 11 in progress after real native build; no verdict or artifact. Trigger retired `62b3c17ef5d5d61aec46591ef0e014d13ef1de7d`.

Configuration continuity regression: exact parent RED 4 restart changes (sampling, timeout, token cap, image permission), mid-call mutation, legacy pending without original configuration receipt. Equivalent reordered sampling control unchanged. Candidate source `52e2234780caa9c05b0dcb10925212c253ddadf3`, tests `2ddb931f3d241eb226158aeabf620a857a741537`: GREEN 94/94 affected tests on exact installed wheel with exact native editor config, real FFmpeg synthetic renders. Persist only configuration digest, check before inference and dispatch; preserve blocked legacy facts/pending. No genuine inference, external provider assurance or independent creative claim.

[Indexed checkpoint retest #45945314825](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45945314825) FAILED, source `a5399047915a2a4061e0a3fe2e1798d0eb77039e`, job 140328553996, artifact #15174959264 ZIP SHA256 `d7a5b31fb4241726e484d3183c98467227301fde3139a4bbfb2ca03e37f55c83` CRC passed. 48 distinct decision turns, 47 provider-reported usage; 547741 reported tokens, 1255093.740ms model wall; 17 searches/178911 tokens/407203.779ms. Two output paths both SHA256 `fe0eaf543c1d558412ed7bb51c8a7fa11268b0d08b5ebf3372600fbccb540d78`; each local full RGB+PCM decode equal; 144 frames at 24fps, 640x360, H.264, 6s, stereo AAC 44100Hz. Original staged and native assets match source ledger; first and second export autosave hashes verified, second only added empty video track. Later text clips at turns 41/42 saved 43, not exported. Local source/first export matched-index RGB MAE 2.635 correlation .999018, zero near-black frames; no trusted general render-origin pixel proof. The journal scope digest identifies project path/timeline ID, NOT timeline content. Earlier times 1/3/5 vs 0/2/4; both numeric full audio reads. No distinct revised media, no semantic hearing, no accepted pair. Do not replay spent trigger.

Stale refusal turns 14/44 followed by unknown-project/asset preconditions turns 45/46. RED on exact installed controller: direct model-selected recovery READ rejected as unsearched, valid grant not visible. GREEN all four controls: selectable exact get_project schema only while stale, valid model choice or decline, no grant/invalid schema refused, valid fresh read removes offer; independent journal audit passes. Source blob `7d2980233ec180e6966336381072fdd4f66caa63`, tests `e01da471962884aeb20fad737b8bd3c8ab69b143`; affected suite 266 run/260 pass/6 missing environment imports/no assertion failures. Candidate not genuine or physical acceptance. Parent loss-aware job 140335168274 failed after successful Vite build; initial HTTP403s recovered, unknown exact silent predicate; one same-source targeted non-model retry requested.

27 Nov exact installed `fd648e50d41cf17ef68815db5e42b683bae1e239` [#45947254432](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45947254432), artifact #15176330121 SHA256 `c90d80223d18a751256774c89246542429ea9f8bb201052689749d165573892c`, local ZIP CRC and 24/24 manifest hashes, exact controller/session source/test hashes and three full physical decodes; merge `0b62e26f6300ac654df43d9cd7b06752fe06ce35` tree `04e4b2c9c72b3054ac2538e7609fb94642da3b6c` equals parent. 1781 tests / 1751 pass / 30 skip / 0 fail. Hosted {"success":28,"in_progress":1}; targeted loss-aware retry SUCCESS. Original loss-aware failure retained. No neural or professional acceptance.

Duplicate export feedback uses existing pair state. RED two tests/three errors; GREEN two tests including missing/unrelated/failed/invalidated controls. Actual trial journal replay true at turn 33 verified duplicate, false at turn 41 acknowledged edit. Pair remains absent. Stale rejection count correction: turns 7, 14, 44. 254 affected tests, 249 pass, five local missing scripts/MCP imports, zero assertion failures. Exact source blobs in ledger; no automatic operations or widened acceptance.

Exact parent `fd648e50d41cf17ef68815db5e42b683bae1e239` completed 29/29 hosted workflows, including terminal MLT #45947253893. Integrated two tested indexed recovery/duplicate feedback corrections at `013ef94d610b63078d39cd38878051367cb6f150`; hosted {"in_progress":2,"success":26,"failure":1} at observation. Desktop #45949362927 first job 140341368353 reached original image-sequence defect reproduction and timed out 124; retry 140343995262 failed at Microsoft apt InRelease HTTP403 before editor launch. No identified product assertion failure, exact first timeout cause unresolved.

New [one-use bounded G1 trial #45950462408](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45950462408), job 140344855257, exact synthetic-only child `e979730bb06ca9e8d7d50d3f689feabb0f2a9597`, parent `013ef94d610b63078d39cd38878051367cb6f150`, retired trigger `8035aa15c424db5d7361a94172a76b15de85e931` restores exact tree. Same 48-turn Super VL indexed trial to test both mechanical corrections, no private egress; actual inference running. No new result or replay.

Coedit revision authority defect (source-shaped deterministic renderer, actual production Python gateway/controller): after model observed timeline, simulated human changed position to 99, host-only style target preflight refreshed model epoch; stale requested position 40 committed. RED both single and combined gateway. GREEN both after separate read-only host-preflight route; stale operation denied before dispatch, fresh independent decision position 100 accepted once. Direct host-only project/timeline read controls cannot mint/renew model revision or invoke ungranted/write tool. Affected 288 tests / 284 pass / 4 missing source-checkout files/imports / 0 assertion failures. Blobs {"studio_next/capability_mcp_session.py":"b4fa08d78eb0580cf85f43faa8126f8b1b49b5b6","studio_next/native_creative_control.py":"eae2274264981af5565a8fdcce42d92e153ac2f8","studio_next/test_native_revision_fence.py":"0018ff84670b529786e67d3829781fcd71e73ee7"}; not physical GUI, genuine human or creative acceptance. Ledger one-space indentation compacts whitespace only, retaining all previous evidence values and hard cap.


## 2026-11-27 — terminal indexed trial and trusted wire refusal

{
  "trial": {
    "conclusion": "failure",
    "artifact": 15177080510,
    "zip_sha256": "2d509a766a1b20ff11fa93c11aaf2c0ca9a29951db9fe5d13d5e78b2b003c5f6",
    "zip_entries": 15,
    "crc_verified": true,
    "decisions": 7,
    "provider_reported_tokens": 56792,
    "model_wall_ms": 297095.356,
    "native_wall_ms": 369.79,
    "searches": 1,
    "write_acknowledgments": 3,
    "exports": 0,
    "saved": "One original six-second video clip; native/staged original hash ea0737ff253bdecd3d730701e6700b04ded8a024eed7715f561a76174f76084d matches; no imported/placed audio.",
    "events": "Turn 3 stale refused, turn 4 fresh get_project, turn 5 search, turn 6 add_asset_to_timeline error classified uncertain and halted.",
    "error_digest": "fdece17a19f0ad9ca8123912e3805daa7620565d17e71c38f824137a4e222a00",
    "diagnosis": "Exact digest of canonical wire list containing fixed placement_plan_unconfirmed BODY message (no timeline edit submitted). Wire/public revision-token digest mismatch reproduced against exact source. Actual raw receipt metadata absent from journal; underlying reason placement preview failed remains unresolved.",
    "independent_acceptance": false
  },
  "wire": {
    "parent": "013ef94d610b63078d39cd38878051367cb6f150",
    "coedit_parent": "c2b75bd84107a2099301ada1676a937d9a5228c7",
    "source_blobs": {
      "studio_next/capability_gateway.py": "7e44a7900df27e48ed9dcf2ad7cf2abb1fb84640",
      "studio_next/capability_attempts.py": "113344a25313cfa7c7f7316b414a924d89622669",
      "studio_next/capability_mcp_session.py": "9b370bac2c7ab68bbcd84ce108bfeb80ae394bd4",
      "studio_next/native_editor_session.py": "5d62c23f5cfec852e1c1b00ce84ad3cc6798bbd6",
      "studio_next/studio_mcp.py": "58675290fcd37c889fe4739e8a2ecdc143c8787c",
      "studio_next/test_body_editor_mcp.py": "e95dbbee21f3699caf01ccbd76f5522b4f443a0f",
      "studio_next/test_native_revision_fence.py": "e74c5fd1ecc811a168c9c0bd3b028d23fb27d9e1",
      "studio_next/test_capability_attempts.py": "12747f59c6c7cbc8b740bd9af83d2c705ecbf2ab"
    },
    "installed_parent": {
      "run": 45949362965,
      "artifact": 15177330866,
      "zip_sha256": "42a30178998882537bd8579ee523b2b1438ec1f037a3032c46c7f6db20fd1cf9",
      "tests_run": 1784,
      "pass": 1754,
      "skip": 30,
      "failed": 0,
      "manifest_verified": 24,
      "physical_mp4_full_decode": 3,
      "exact_equal_tree": "abf2171f93b095e31775a4f73fcdafa4c9e0d846",
      "merge_test_commit": "678bdd5a2d1527f8a343acf87159305ac45372ac",
      "crc_verified": true,
      "local_wheel_source_hashes_verified": true,
      "hosted": {
        "success": 28,
        "failure": 1
      }
    },
    "reproduction": "Four assertion failures on original behavior: exact trusted wire refusal falsely uncertain in both routes, forged public-input receipts falsely accepted. Underlying preview reason not proven.",
    "correction": "Explicit trusted local editor source only; strict error and exact augmented wire digest, immutable expected input snapshot; gateway rebinds verified refusal to public input, preserves prior observed epoch; strips reserved untrusted metadata. Durable terminal host_rejected_no_native_write distinct from conflict/uncertainty; migrate V1/V2 without losing attempts, preserve no replay. No grant expansion, auto retry, or acceptance relaxation.",
    "verification": {
      "focused": "Seven refusal controls GREEN plus stale human edit after safe refusal; physical SQLite V2 migration and replay prevention GREEN.",
      "run": 325,
      "pass": 286,
      "skip": 36,
      "errors": 3,
      "assertion_failures": 0,
      "limitations": "Optional MCP SDK unavailable locally (36 skips including new real HTTP/SDK test); three missing checkout script imports. Hosted SDK and native evidence pending."
    },
    "next": "Verify exact-head CI and real SDK bridge; diagnose desktop physical test separately; continue critical-path genuine creation/revision/human coedit then matched routes/A-L independent acceptance. No repeat of spent trigger and no further inference before corrected evidence.",
    "independent_acceptance": false
  }
}

### Retained historical delivery-affordance receipt

Exact structured value moved from mutable ledger for bounded size; original blob `c823687f0d9e4b84341a5ebaf43a8eba2e6d53cd` remains available.

```json
{
  "baseline": "385534021c47efdecf70685e5f54095ea37e3d2d",
  "source_blobs": {
    "studio_next/native_creative_control.py": "7e72f643708623936e617d59360382c7fa5df10e",
    "studio_next/test_native_creative_control.py": "63bc3c1ac42bed39d91bcc501dd14a3270a7672e"
  },
  "negative": {
    "real_run": 45731089541,
    "artifact": 15078171115,
    "sha256": "47c46e631c1cd6e691199d906a3c4ab4c5e1134573ad049f335b61fd328c35f0",
    "facts": "88 events, 37 decision turns, 14 searches, 2 stale source refusals, save at turn 31, search again at 32, zero exports. Exact causal contribution of visibility not established."
  },
  "correction": "Expose one already-granted source-bound save/export/verify affordance from positive live clip count, current save and latest captured render. No automatic native action, grant or artistic choice; current destination evidence stops repeated verify visibility.",
  "matched_scripted": {
    "baseline_delivery_decisions": 6,
    "candidate_delivery_decisions": 3,
    "identical_native_call_sequence": true,
    "red": "4-turn baseline executed save and render but exhausted before verify",
    "green": "Matched controller and auditor fixture passed, including missing/empty project, capture disabled, invalidated evidence, malformed capture, wrong grant and later edit."
  },
  "local": {
    "run": 223,
    "pass": 217,
    "assertion_failures": 0,
    "environment_import_errors": 6,
    "limitations": "Reconstructed exact parent blobs from installed wheel; no complete checkout, MCP SDK or repository-only scripts. Actual local model/provider absent."
  },
  "acceptance": {
    "exact_candidate_ci": "29/29 SUCCESS at fce6049bbee21ad65a3421e383a862644d1aa364; genuine indexed trial FAIL (see indexed_trial)",
    "genuine_model": false,
    "professional": false
  },
  "next": "Both single arms failed final completion. Direct mode removed 17 searches and reached transient reviewed pair, with 2.23x reported tokens and less wall time. Do not infer statistically proven architecture preference. Inspect completion/revision handoff and stale filename correction; no paid blind rerun.",
  "parent_installed_artifact": {
    "run": 45932518653,
    "artifact": 15169717251,
    "source_commit": "f4fb523f0c4c0334cb2e8f514092c3d74093318e",
    "tree_equivalent_to": "385534021c47efdecf70685e5f54095ea37e3d2d",
    "sha256": "4130f18bdbda3cbf91262384a144e4f6360394983e1625f978756e0bfcc62f87",
    "manifest_verified": 24,
    "tests": {
      "run": 1757,
      "passed": 1727,
      "skipped": 30,
      "failed": 0
    },
    "physical_decode": "Full mixed:57 frames 320x480 4.75s AAC stereo 48k; 2D:33 frames 320x480 2.75s AAC stereo; 3D:24 frames 256x256 2s video-only; full FFmpeg decode successful. Scripted physical proof only."
  },
  "indexed_trial": {
    "run": 45934918405,
    "source": "c5d5de094f6d61e181b5c10088b47cf68d646a19",
    "revoked": "1096550254f2e5c59c621880d3de171eec0716f8",
    "artifact": 15171390542,
    "sha256": "c1f880a29113a4ffa967deebf66a7be7544f51b7110986bdb5fec2f510ddde86",
    "status": "FAILED: turn_budget_exhausted, no second export/pair",
    "events": 117,
    "turns": 48,
    "searches": 17,
    "reported_tokens": 589619,
    "search_tokens": 212272,
    "model_ms": 1026490.065,
    "native_mcp_ms": 1925.473,
    "write_acks": 11,
    "export_verified": 1,
    "first_export_sha": "fe0eaf543c1d558412ed7bb51c8a7fa11268b0d08b5ebf3372600fbccb540d78",
    "receipt": "ZIP CRC+SHA match; independent ffprobe and full FFmpeg decode 640x360 H264 24fps 144 frames/6s AAC; saved native source SHA verified; no rendered-original pixel proof, semantic listening or quality approval."
  },
  "direct_trial": {
    "run": 45937037913,
    "source": "e4abbd93c6aa82a3593e1014dd069fac05d68f23",
    "revoked": "9d27019f0a8b2e0aecd29ad954cc4cbc51322807",
    "same_runtime_parent": "fce6049bbee21ad65a3421e383a862644d1aa364",
    "request": "ZX7_SUPER_VL_G1_DIRECT_CATALOG_20261127",
    "status": "FAILED terminal turn_budget_exhausted; transient pair passed then revoked by later model edit",
    "scope": "Same source/model/brief/48-turn budget; only existing full vs indexed catalog route changes. Whole-interface comparison, not single-factor internal ablation or repeated controlled trials.",
    "artifact": 15171327555,
    "sha256": "438d92a0b030ace86723a61aafc03b8cf91618d80207eb2e283601e8fcd0c684",
    "events": 135,
    "turns": 48,
    "searches": 0,
    "reported_tokens": 1315967,
    "reported_prompt_tokens": 1251098,
    "reported_completion_tokens": 64869,
    "model_ms": 578863.636,
    "native_mcp_ms": 3390.493,
    "write_acks": 14,
    "export_verified": 2,
    "export_shas": [
      "9da3574b0244e54cfbc9131d3f61482f2a132e7106a93721b22f49c411f8afbd",
      "31391ea2abd493e461b3d597cb97c611b9dbe9e89c00c3a04d34c08bed3c8cd7"
    ],
    "saved_render_shas": [
      "29d6785bd0dee6e0c3288a4730f555b1734190e596a79cf65b121d0007b9b893",
      "8ff5dc05b4bcae9256b87d98825606a6c0afbdefe63820fb6b37a5e97b600561"
    ],
    "prefix_observation": "Actual pair comparator returns both exports after turn 41/seq 118, and None after turn 42/seq 120 acknowledged text edit; final two exports rejected output_exists; no automatic replay. Exact retained render-time autosave hashes match. Independent ffprobe and full decode both six-second 640x360 H264 24fps 144 frames, 79/144 RGB frames differ, identical decoded AAC PCM, RMS 0.05555946. No final model finish, semantic hearing, independent quality or rendered-original pixels proof."
  },
  "checkpoint_followup": {
    "observed": "Direct model received turn index, not configured remaining turn budget; at turn 42 six decisions remained after actual prefix pair readiness.",
    "change": "Expose host-verified current-required-evidence boolean and exact max/remaining decisions; compute missing evidence once, preserve independent finish/revise choice, later-write invalidation and actual grants.",
    "red": "Missing decision_turn_budget KeyError",
    "green": "Model fixture chooses additional edit after readiness; evidence revoked, reverified, independently finishes. 215 affected run/210 pass/5 missing MCP and repo script import errors; zero assertion failures.",
    "acceptance": "Local protocol only; genuine benefit unverified, no new paid inference."
  }
}
```


## 2026-11-27 — placement refusal source observations and SDK verification

{
  "parent": "95d841a46af61e9b0c2beafdfd0971ad61e8474d",
  "source_blobs": {
    "studio_next/native_creative_control.py": "bf18e7b4bd1d6f9d6edf752379c49f92fdd3eab8",
    "studio_next/test_native_creative_control.py": "e70e8ba5d66f5db1f78b1f76772fc2e99054a68d"
  },
  "negative": "Exact canonical source: after a trusted placement_plan_unconfirmed refusal, cached native asset/track selection still points at prior source. Independent RED controls: explicit model-selected get_assets recovery rejected as unsearched; decline further reads control still advertises asset-old instead of actual asset-new. Deterministic source-shaped fixture, not diagnosis of original native preview error.",
  "correction": "Clear stale placement/read snapshots and prior result/preview text after confirmed no-write placement denial. Offer installed schema-valid granted get_project/get_assets/get_timeline in indexed recovery frontier; no added grant, automatic model action or placement retry. Existing bounded host reads refresh their own observations; preserve immutable journal/last acknowledged write.",
  "local": {
    "run": 272,
    "pass": 269,
    "errors": 3,
    "assertion_failures": 0,
    "limitations": "Three missing scripts.run_native_model_trial imports in installed-wheel-only environment. Focused GREEN with no-grant, invalid-schema and model-decline controls; no real neural or GUI acceptance."
  },
  "hosted_parent": {
    "observed": {
      "success": 25,
      "in_progress": 3,
      "failure": 1
    },
    "real_sdk": {
      "run": 45952719717,
      "job": 140352046550,
      "passed": [
        "test_cas_placement_preflight_receipt_survives_actual_sdk_gateway",
        "test_wire_bound_placement_refusal_is_not_an_uncertain_write",
        "test_controller_clip_style_preflight_cannot_refresh_stale_model_epoch",
        "test_revision_schema_migration_preserves_uncertain_and_confirmed_intents"
      ],
      "limits": "Real HTTP/MCP SDK bridge; source pin fixture. 346-test SDK group and 271-test gateway group completed; not actual human study."
    },
    "desktop": {
      "run": 45952719679,
      "job": 140352046121,
      "conclusion": "success",
      "previous_failed_parent": 45949362927
    },
    "research": {
      "run": 45952719864,
      "job": 140352046589,
      "conclusion": "failure",
      "detail": "17 of 18 live provider/language checks passed; Europe PMC unavailable or invalid JSON, underlying transport cause not logged. Existing same-URL timeout retry only, no blind rerun."
    },
    "running": [
      45952719857,
      45952719639,
      45952719866
    ]
  },
  "next": "Preserve pending exact parent physical/installed/MLT gates, integrate this tested candidate with exact head lease after terminal. Review actual provider availability and native placement preview cause without guessing from redacted journal. Genuine G1, human coedit, G2, A-L professional and release acceptance remain open; no new model spend."
}

### Retained historical timed-feedback structured receipt

Original ledger blob `fdfef087c1d7603731d2e96fab969f04cbff7e34`; exact original structured value retained below to preserve the bounded mutable ledger.

```json
{
  "baseline": "f676146e7a95da42fd39eb62d72154e2bce1af54",
  "source_blobs": {
    "studio_next/native_creative_control.py": "8445235d5b213d36d36fba51e0e05e69bd623aab",
    "studio_next/test_native_creative_control.py": "56cd5068850e12a04a9027cbcb565953c4a4c8bf"
  },
  "causal_gap": "Source-derived counterexample: a single still plus full numeric audio hid remaining separated timed-picture requirement from the indexed model frontier. This is an interface gap, not proof that it caused any historical trial failure.",
  "correction": "Retain generic still evidence; report separated source-bound timed sample coverage independently and keep the already-granted timed read selectable. The pair acceptance gate, native writes, authorization and artistic judgment are unchanged.",
  "local": {
    "red": "Source-derived isolated method reproduction: still incorrectly counted as timed readiness; assertion failed.",
    "green": "5/5 scoped Python excerpt tests passed, including narrow/invalid/mismatched samples, combined window, failed read and write revocation.",
    "limitations": "No repository checkout in current runtime; connector-only source access and no GitHub DNS. Full integrated controller regression and actual CI pending."
  },
  "acceptance": {
    "exact_source_ci": "24/29 SUCCESS; 5 FAILURE at d2ecb848f6f0df7734c9a2a94d1651789a6db0da",
    "genuine_model": false,
    "professional": false
  },
  "next": "Verify exact candidate CI. Only after stable baseline, qualify actual model/provider and creative interface; no connector dispatch.",
  "hosted_regression": {
    "source": "d2ecb848f6f0df7734c9a2a94d1651789a6db0da",
    "success": 24,
    "failure": 5,
    "runs": [
      45926146560,
      45926146497,
      45926146559,
      45926146423,
      45926146408
    ],
    "observed": "test_indexed_same_time_av_comparison_keeps_verified_native_reader_visible: already_comparable and invalidated_by_write expected TIMED_FRAMES absent, actual present; Python 3.11–3.13 and shared suites.",
    "diagnosis": "Older pair fixture uses abbreviated image hashes, stricter readiness requires 64-character digests. Source-supported candidate explanation; write invalidation needs independent reproduction. Not a proven root cause.",
    "genuine_model": false,
    "professional": false
  },
  "fixture_correction": {
    "parent": "5023d44e125c60ce895de35493b8c953c53cb98c",
    "source_blobs": {
      "studio_next/test_native_render_evidence.py": "0d8c5070ca933a8b5d696a5fcd1f41e62a4dd668",
      "studio_next/test_native_creative_control.py": "2350a20114e9555dcccff9fe816c23b8b5e157b8"
    },
    "cause": "Shared old pair fixture used one-character hashes; invalidation injected add_text_clip absent from fixture write grants. Source-derived isolated current-evidence reproduction: two original assertions fail; realistic hash and admitted update_text_clip ACK pass both. No production validation relaxed.",
    "verification": "Exact parent 385534021c47efdecf70685e5f54095ea37e3d2d 29/29 CI SUCCESS (actual model jobs skipped); revision and Omni Python 3.11–3.13 passed; source apt missing ffmpeg recovered on targeted unchanged-source retry. Actual controller RED/GREEN 11 tests; previous broader run 222 run/216 pass/6 environment import errors, no assertions failed. Details PR #356 comment 7208810798.",
    "next": "Baseline technical regression closed; no genuine model or professional acceptance."
  }
}
```


Physical recovery fixture source blob `739a9aa118a82fe8382d350be78e1282c4288c21`: two actual denied native source placements through model-facing trusted gateway, fresh asset/project reads, subsequent independently selected fixture placement on existing native timeline. Asserts no clip on denial and exactly one subsequent acknowledged write and observed clip. New async block syntax checked, actual Electron execution NOT yet run on candidate. Parent observed {"success":26,"in_progress":2,"failure":1}. No new inference.


## 2026-11-27 — Field F native HDR picture capability

{
  "parent": "f2da4f904981ccb56a4f4b4acbc7405158734c9c",
  "domain": "F",
  "outcome": "Extend existing real owner EXR-to-ProRes instrument to explicitly selected ACES2 Rec.2100 PQ 1000-nit-target Rec.2020 picture delivery, keeping SDR and separate audio. New capability, no second renderer, no model-specific behavior or preset art.",
  "upstream": {
    "url": "https://github.com/AcademySoftwareFoundation/OpenColorIO/blob/v2.5.0/src/OpenColorIO/builtinconfigs/configs/cg-config-v4.0.0_aces-v2.0_ocio-v2.5.ocio",
    "blob": "6abfcf9cd10dad204d519725d9925239aca767e0",
    "display": "Rec.2100-PQ - Display",
    "view": "ACES 2.0 - HDR 1000 nits (Rec.2020)"
  },
  "source_blobs": {
    "studio_next/body_aces2_movie.py": "f70058d92f5e4451fb34931a56ebc85cbd2e9ed9",
    "studio_next/body_aces2_preview.py": "d1fe5750b4b09241f6a08ee0f025643a7fd7a967",
    "studio_next/body_document_schemas.py": "73c0109531af349c63107819cfdc53194c256f47",
    "studio_next/body_integration.py": "5865097bcce2705274a32db97757e8958c6e7a06",
    "studio_next/test_body_aces2_movie.py": "a704e2067f1272493d05f6ed0a49f276d538bee2"
  },
  "negative_controls": "Initial RED: missing codec route; actual FFmpeg 7.1.5 rejects bt2020nc scale enum (bt2020 required), then encoder omitted stream primaries/PQ despite requested tags. Frame-header bitstream filter alone did not fix MOV stream. SDR raw codec also omitted primaries on this version. Correct fixed allowlisted scale matrix, setparams per-frame color and range, HDR ProRes metadata and independent stream+every-frame validation. Wrong display/view pairs rejected before encoding.",
  "local": {
    "focused": 4,
    "focused_pass": 4,
    "affected_run": 24,
    "pass": 15,
    "skip": 9,
    "fail": 0,
    "actual": "Three-frame 96x32 12fps 10-bit ProRes422 HQ; actual decoded ST2084 grayscale patches 0/1/10/100/400/1000 nits target (code-value oracle tolerance 3) and independently calculated Rec.2020 chroma (tolerance 4), all native frame tags; SDR real 2-frame decode and schema controls passed.",
    "limits": "No OpenEXR/OCIO/Blender stack in local runtime; package install unavailable. New native EXR->ACES2 PQ->ProRes test uses actual native Blender, original source rights and separate processor/luma oracle; hosted proof not yet run. Existing 2M total-pixel session bound, picture only, no calibrated monitor/HDR10 static metadata or independent field acceptance."
  },
  "previous_parent": {
    "head": "95d841a46af61e9b0c2beafdfd0971ad61e8474d",
    "hosted": {
      "success": 28,
      "failure": 1
    },
    "failure": "Europe PMC live research",
    "artifact": 15178505885,
    "zip_sha256": "17aa042a3f071296a7529bc908d386d7a2badb769f41d1788155cccaff3a591f",
    "manifest": 24,
    "tests_run": 1789,
    "pass": 1759,
    "skip": 30,
    "fail": 0,
    "full_decodes": 3,
    "merge_tree": "a0bf1439258f05c66b696e9bc5b776f87b4813ca"
  },
  "next": "Run isolated real native stack physical proof of new field capability without cancelling active canonical hosted gates. Integrate verified capability with exact branch lease when stable. Continue independent A-L capabilities, preserve G1 actual creative and human acceptance; no new paid model, no claim F accepted."
}

### Retained historical perception and exact lookup structured receipt

Exact value from prior ledger blob `566c8d86dd1097e88fa4e3d2f5686ea2c37c4701` retained for bounded mutable ledger.

```json
{
  "parent": "21bac3469fe6d87c630fd66178f5c17796b3810e",
  "previous_exact_head_ci": {
    "success": 28,
    "failure": 1,
    "failed_run": 45939750087,
    "failed_job": 140311086464,
    "reason": "Europe PMC repeated timeout after bounded retry; 31 offline research tests passed. Do not weaken live gate or rerun blindly."
  },
  "visual": {
    "model": "NVIDIA Super VL",
    "source": "95eb692104bc88d042f7203a90ea6b9121b6f4f6",
    "script_blob": "74e302d369fa1709a0ddfe6b7ecbf593dabd07df",
    "run": 45941783748,
    "job": 140317496319,
    "artifact": 15173003314,
    "sha256": "fa09a74be694c973e9b55e4f3c7aa85970adc5e1203c0fa422e2735b13ac28df",
    "retired_trigger": "eea64016d32165400a576a5dacea88f0ef706891",
    "passed": 5,
    "cases": 5,
    "reported_tokens": 15047,
    "model_wall_ms": 29442.041,
    "independent": "ZIP SHA/CRC; five full MP4 decodes; 15 PNG hashes and independent RGB equality; numeric audio peaks and case oracle verified. Aligned, offset, sound-only, neither, picture-only typed observations.",
    "limits": "Basic sampled visual and numeric audio-bin recognition only; no continuous motion, semantic listening, full artistic or G1 acceptance."
  },
  "raw_audio": {
    "model": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
    "source": "aa8c21526f6f12dab636f61ef5becfb59b3fd5db",
    "script_blob": "1ce7960163fc918db11978d9082a58ac0407b6f4",
    "run": 45942171828,
    "job": 140318717014,
    "artifact": 15173153626,
    "sha256": "8c1540adbf8787325ac077d1c3c9d1d29fed8aed7d19b09e4b1f4b49524144c6",
    "retired_trigger": "e0fc18741813bccd12ac1daab9e16006e226adce",
    "offline_tests_passed": 47,
    "passed": 1,
    "cases": 4,
    "reported_tokens": 4351,
    "model_wall_ms": 4375.409,
    "expected_hz": [
      [
        880,
        440
      ],
      [
        0,
        0
      ],
      [
        440,
        880
      ],
      [
        440,
        440
      ]
    ],
    "observations": [
      "rising",
      "silent then high/rising",
      "rising",
      "rising"
    ],
    "independent": "ZIP SHA/CRC; all four full MP4 decodes; source and WAV receipt hashes; independent 16kHz mono 2s PCM byte-identical to retained WAV, FFT verifies pitch and silence. Typed transport succeeded; wrong model reports remain failure.",
    "limits": "Single four-case calibration at this model and prompt; no proven semantic hearing, no cause attribution between service internals/model. No blind retry."
  },
  "index": {
    "hypothesis": "17 indexed searches returned 101 name occurrences, 23 distinct, 78 repeats. Exact already-granted IDs can reduce discovery ambiguity without full schema dump. Genuine efficiency not yet measured.",
    "source_blobs": {
      "studio_next/capability_fabric.py": "8dd3cac29c9308f4970b64480b2c4ee2c5e187e9",
      "studio_next/native_creative_control.py": "7b343d1100a4cf9c92bc492aa2d9bdcf25c6888c",
      "studio_next/test_capability_fabric.py": "39f5f44f181d91670f76c1476ef48f7ae90c36b4",
      "studio_next/test_native_creative_control.py": "c014d18b96d8f3c64aa5cdb290772d0e2ee27a50"
    },
    "change": "Complete or absent retrieval-only exact ID index, <=48 operations, <=4096 serialized bytes, queryable <=160 byte IDs; no new schema, grant or dispatch. Large catalog unchanged.",
    "red": "Missing exact_lookup_index and model context field",
    "green": "Three focused tests passed including large catalog no dump; unselected invoke blocked; exact lookup collision qualification and bounds tested.",
    "local": {
      "run": 250,
      "passed": 243,
      "environment_errors": 7,
      "assertion_failures": 0,
      "limits": "Reconstructed exact parent blobs; absent MCP SDK, repository scripts and example config; no full checkout."
    },
    "hosted": {
      "head": "d48af496fa70a9208a94016fd5e4d7320d05d0e1",
      "counts": {
        "success": 28,
        "in_progress": 1
      },
      "installed": {
        "run": 45942606959,
        "artifact": 15174550542,
        "sha256": "47d53ab4716c683965ba41832323d8a9815234097facb64d53b0c9851788e788",
        "merge_commit": "10afc0a827195f3d7e5d3ae90a3d271af1ee87a4",
        "exact_tree_equivalence": true,
        "manifest_verified": 24,
        "tests_run": 1775,
        "passed": 1745,
        "skipped": 30,
        "failures": 0
      },
      "native_conflict": "Installed cross-process job 140320939079 initially refused stale add_assets_to_timeline at commit boundary; targeted unchanged-source retry successful. No proof exact cause; no safety relaxation."
    },
    "genuine_model_benefit": false
  },
  "next": "Use measured compositional route for real-model matched G2 experiment only with valid bounded scope and comparable native outputs; do not conflate synthetic speech recognition with music comprehension. Verify genuine current-project completion, human coedit and independent quality.",
  "speech": {
    "model": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
    "run": 45944055906,
    "job": 140324606233,
    "source": "b282fd85606c38b87be2411833f092fe628da6a3",
    "script_blob": "5a3ea4893b1a2364386996329ba02bae54a5d444",
    "retired_trigger": "b0afff228fbf84f32a18e03252ec3bec59ee75e5",
    "artifact": 15174256003,
    "sha256": "a71c16e0191a302d53ff091b8a154bb3f27b8b09786fea99a3362d32af6c2352",
    "passed": 4,
    "cases": 4,
    "reported_tokens": 3785,
    "model_wall_ms": 5219.613,
    "observations": [
      "silver moon",
      "",
      "paper boat",
      "winter rain"
    ],
    "independent": "ZIP CRC/SHA verified, four complete physical MP4 decodes and WAV+PCM hashes match; independent 16kHz mono decode byte-identical. Silence RMS zero.",
    "limits": "Short English synthetic speech/silence discrimination only. Prior pitch failure stands; no general musical or artistic competence inferred."
  }
}
```


## 2026-11-27 — native Field F terminal proof and Field G timed-text delivery

{
  "field_f": {
    "run": 46004334436,
    "job": 140523578984,
    "source": "d2bbcfbf106d02e1a4ca60514e2a8c51daaf2233",
    "retired": "383cb74eaeae9900792cc418141eb8069e45d362",
    "conclusion": "success",
    "artifact": 15200411017,
    "zip_sha256": "f90e4b1f1885b05c2e53d3daba0b6a49d08a7150f219918be6cd29af1c60ff3b",
    "manifest_verified": 4,
    "full_decode_verified": true,
    "native_blender_exr_ocio_luma_oracle": true,
    "output_sha256": "5fc1620cf70022476b33622d203fc352638cf593e7f689b8c9aa534748375850",
    "original_exr_zip_sha256": "825ae36622e52d201fe7c6d9458313abb77459443b9c6caf951712e099956251",
    "actual": "96x64, 2 frames at 12 fps, ProRes HQ yuv422p10le, Rec.2020/PQ, both frames limited range verified locally. Actual native Blender/EXR/OCIO pipeline passed hosted; no calibrated monitor or professional acceptance."
  },
  "field_g": {
    "parent": "ec0b8a4bd9bd9d2cc0aad612225b169b56344092",
    "domain": "G with F crossover",
    "outcome": "New typed body.subtitle_delivery instrument: explicit multilingual plain-text millisecond cues -> real selectable native MOV/MP4 timed-text tracks, source picture and every audio track preserved by encoded packet/timestamp/side-data and decoded A/V equality. Original media rights and atomic publication reused. No caption text or artistic decision authored by host.",
    "source_blobs": {
      "studio_next/body_subtitles.py": "28e3db1fb1aa7b1eb02e19545374abd481ebf47d",
      "studio_next/test_body_subtitles.py": "0e4cc7c53375e0002a9bb68798ef421d0a39c9a9",
      "studio_next/body_integration.py": "940d31d5bcba0222229bc997d83b6b5c93998ff1",
      "studio_next/body_document_schemas.py": "f0ffbd6adc8915d3c33d1bb45f63dcc578aca9f4",
      "studio_next/body_materials.py": "e5a40e621e89d147fbd95f203ae652aac1196198",
      "studio_next/creative_tool_registry.py": "84613a873aff66ab2c17b35a38ebbc836cccd611",
      "studio_next/test_body_shared_revision.py": "ecbf9a21109fe5e95fa946f0c5bd31bd2679b71f"
    },
    "baseline": {
      "head": "f2da4f904981ccb56a4f4b4acbc7405158734c9c",
      "hosted": {
        "success": 28,
        "failure": 1
      },
      "research": 46003188695,
      "installed": {
        "run": 46003189228,
        "artifact": 15201666345,
        "zip_sha256": "3192528cd444cdca5f20b947e93f520388c9fe1a8942ab717f94c2d1a57ad6bb",
        "merge": "aa75ed4f2f8bd3516ee9bdf107f7cbc7026c212e",
        "exact_tree": "623e09102f0bf5e8207fe293dcfef7e273613cda",
        "tests_run": 1790,
        "pass": 1760,
        "skip": 30,
        "fail": 0,
        "manifest": 24,
        "full_decodes": 3,
        "crc_verified": true
      },
      "placement": {
        "run": 46003188906,
        "job": 140519767636,
        "actual_native_gateway_placement_recovery": true,
        "fixture_only": true
      }
    },
    "negative": "RED two Unknown tool errors on actual native source. Native QuickTime silently marked lone subtitle default despite explicit disposition 0; observed on actual F HDR master. Refuse zero or multiple defaults instead of choosing. Fault-injected actual AAC reencode and changed text both rejected before publication. Invalid overlaps, duration, markup, missing rights and preexisting subtitles rejected; no overwrite.",
    "verification": {
      "focused": 5,
      "affected": 15,
      "pass": 15,
      "fail": 0,
      "local": "Actual H264 24000/1001 160x96 film with two AAC tracks 48k/44.1k; selectable English/Hindi UTF8 text and exact millisecond cue roundtrip; independently equal decoded video and both float64 PCM streams. Real ProRes HQ PQ 10bit MOV silent source passes, original color signaling and source hashes preserved. Earlier broader local run interrupted after 24 completed passing tests; not a full suite.",
      "cross_field": {
        "source_artifact": 15200411017,
        "source_sha256": "5fc1620cf70022476b33622d203fc352638cf593e7f689b8c9aa534748375850",
        "captioned_sha256": "96ab6885b18dedbf6b90d085cef486b0d66c59cfcc328345b4c2c027bb8472b1",
        "actual": "Local real hosted HDR master remux with authored text 0-150ms; same 2 picture frames, PQ/Rec2020 tags, no fabricated audio."
      },
      "limitations": "One zero-origin picture, optional multiple audio; same MP4/MOV container, no preexisting non-AV streams or chapters; 1-8 tracks, one explicit default, plain text only, bounded author plan. No automatic transcription, translation, style, accessibility, GUI editing proof or independent Field G acceptance. Exact combined hosted suite pending."
    },
    "next": "Integrate F+G coherent increment on stable branch with exact lease. Advance other A-L missing capabilities while hosted runs; preserve genuine creative and independent professional acceptance."
  }
}

### Retained historical indexed-duplicate-feedback-20261127

Exact structured value from prior ledger blob `38959fe180502cacba095f8d49f17868a91821e7` retained to respect ledger cap.

```json
{
  "parent": "eb565a7a3da256532d89b6b2eff6bc1edd82b919",
  "source_blobs": {
    "studio_next/native_creative_control.py": "c85094fefa0d1cbcde696ed2e7a7f271d46208b9",
    "studio_next/test_native_creative_control.py": "a53f4416d0cc03cce19bc1828e75f9bca3181cc5",
    "studio_next/native_render_evidence.py": "965f03986d55493fed8c16620222d6ca1c4d8429",
    "studio_next/test_native_render_evidence.py": "3ad14cfa04ddb30e6b531e8f9b7dab938b67616e"
  },
  "negative": "Real trial duplicate export at turn 33 not explicitly identified against prior fully reviewed same-scope bytes. Existing pair gate refused completion. RED two tests, three missing contract errors.",
  "correction": "Reuse existing scoped, invalidation-aware pair state to report current verified export matching prior reviewed bytes. Does not count new perception, suppress reads, choose edits, grant completion or infer equivalence of different encodings.",
  "verification": "Two focused tests GREEN, controls for distinct/absent verification, unrelated scope, absent prior complete A/V review, failed read and later write. Replay of original journal shows true immediately after verify turn 33 and false after new write turn 41; pair remains absent. Affected suite 254 run/249 pass/5 missing scripts or MCP imports/zero assertion failures.",
  "installed_parent": {
    "head": "fd648e50d41cf17ef68815db5e42b683bae1e239",
    "run": 45947254432,
    "artifact": 15176330121,
    "zip_sha256": "c90d80223d18a751256774c89246542429ea9f8bb201052689749d165573892c",
    "tested_merge": "0b62e26f6300ac654df43d9cd7b06752fe06ce35",
    "tree": "04e4b2c9c72b3054ac2538e7609fb94642da3b6c",
    "local_manifest": 24,
    "tests": 1781,
    "passed": 1751,
    "skipped": 30,
    "failed": 0,
    "local_decode": "Three complete H264 exports: mixed 320x480/57 frames/4.75s stereo AAC 48kHz; 2D 320x480/33 frames/2.75s stereo AAC 48kHz; 3D 256x256/24 frames/2s video only. Exact installed controller/session source and test blobs match parent.",
    "hosted": {
      "success": 29
    },
    "loss_aware_rerun": "SUCCESS",
    "mlt": 45947253893
  },
  "next": "Advance coherent tested candidate without cancelling parent verification. Actual neural improvement, human co-edit and professional acceptance remain unproved; no new inference or grant."
}
```


## 2026-11-27 — native armature, exact owner rights withdrawal, genuine G1 retest

```json
{
 "field_e": {
  "scope": "Field E: explicit native armature bone authoring in existing Blender .zxmotion transaction, plus real skinning and pose revision using existing RNA operations; no new renderer or arbitrary operator execution.",
  "candidate": "d46131754ed2576b7f09e263522165f3dda06ce8",
  "blobs": {
   "studio_next/body_motion_project.py": "5a33401f16b4af21aa64a63363de13ca16e83e18",
   "studio_next/body_motion_worker.py": "850523ada879d7c827768b15cd9ff1493e72d017",
   "studio_next/test_body_armature.py": "1ca90c42444d4738408a3f6da95f2e490b678e63",
   "studio_next/body_integration.py": "dbb71f802b8d3ca93361d617120c8b55f8d6853d"
  },
  "validation": "1..1024 authored bones; finite rest coordinates, nonzero length, exact UTF-8 name, unique, acyclic known hierarchy, connected endpoints. Empty local single-user armature, synchronized active view layer; preserve selection/active state, check actual created hierarchy and rest coordinates. No autonomous authored weights or pose.",
  "negative": [
   {
    "run": 46008340382,
    "job": 140537109338,
    "result": "checkout failed before tests: missing HEAD^; fetch-depth corrected",
    "source": "dab4407f60de18b30de9091aef5c4575a43e17b5",
    "retired": "4d9dbcc24ff6c009209066320d7f5f749072c6b6"
   },
   {
    "run": 46008559626,
    "job": 140537849055,
    "result": "26 pass/1 failure, native object after link not yet visible to eligibility check; explicit view_layer.update(), retain all guards",
    "source": "6a18bb48cec0ee52d47c45b3c7a25375deb9c317",
    "retired": "a23e58aeb4c474f6a40e77c01e081ee0e0e3cebe"
   }
  ],
  "actual": {
   "run": 46009156855,
   "job": 140539900861,
   "source": "4a7f9b506d03d25347c62a6486cb69ab40379525",
   "retired": "4b7040e67ae5860129bd94908403f40572f08ac4",
   "artifact": 15202706426,
   "sha256": "f584513694b543388f5d7ef0a84d986e99062cd090cbdf0beed8c382837c5a08",
   "crc": "PASS",
   "manifest": "6/6 verified",
   "blender": "4.5.16 LTS",
   "original_bundle": "9a755ab96883410e0a0534b14ea9abc3a032233688e09e4d35883f3456a039d3",
   "child_bundle": "44e29e7a8bb7ec355719cfe19ede9101ee076631ea6a862030b53f60b37c82e4",
   "original_blend": "2cf9c8d22873ce54698cfba649f912747b04d07e390f03e38a38865148df8d78",
   "child_blend": "9b1f579d114a4af24258104ce16731030fb95b3cf61c54b5a49425c9d4b2f174",
   "reopen": "independent native process confirms Root/Tip hierarchy, full Tip skin weights, modifier, evaluated geometry and parent digest; frame 5 original x=-1 vs revised x=1; independent maximum numeric error 1.1920928955078125e-7"
  },
  "archive_fix": {
   "studio_next/body_archive.py": "d298beba7a4362c61cf0cb673accad14591257be",
   "studio_next/test_body_archive.py": "e9fb27997fe068b737dfed90596b83aa77b1c871",
   "scope": "Exclude subtitle staging prefix .zx7-subtitle- from archive"
  },
  "limits": "Not full rigging, IK, character animation, rendering, artistic control, neural or professional acceptance."
 },
 "field_a": {
  "scope": "Field A: irreversible exact-attestation withdrawal for future admissions in the current vault, via owner-authenticated quiescent service and zx7-client withdraw-rights. Existing SQLite authority, no separate registry, no model write grant.",
  "blobs": {
   "studio_next/media_vault.py": "b35fee6f64eb6a0efe4c8571c3ef152e969c81c4",
   "studio_next/body_materials.py": "61a26f66b9f66b2b8b58c2a320eebe5a65943732",
   "studio_next/body_service.py": "44b47388f428d1693acd1b3b5baf4ad3b722bc41",
   "studio_next/body_client.py": "8404e65b625f9b07dea2e8bcbdd286c111f474f0",
   "studio_next/test_body_rights_withdrawal.py": "48f74f04d9e36b42384b9dea04a7551dad15d50b"
  },
  "negative": "Missing withdrawal and legacy material fingerprint reproduced. Checkout withdrawal after last inspect denied at final transactional publish. Initial restore test wrong path denied as designed; corrected test restores exact original path.",
  "proof": "62/62 local affected tests, including actual FFmpeg native subtitle delivery, withdrawn fresh and cached graph admission denied, prior delivered bytes unchanged; exact reingest refused, independent active grant retained, immutable reason/time, post-withdrawal backup/restore retains tombstone, unauthorized owner HTTP 401, active workspace job denied, idle owner success.",
  "route": "POST /v1/workspaces/{workspace_id}/rights/withdraw",
  "limits": "No recall of historical exports, raw/non-attested paths, derivative propagation, other independent grants, externally copied media, or pre-withdrawal backups; no complete license/professional acceptance. Hosted combined proof pending. Additional broader local material suite timed out before terminal result; no pass claimed."
 },
 "g1": {
  "run": 46007258095,
  "job": 140533444321,
  "source": "c29c135f96bf6d25658b3fd830245c907119ea2c",
  "parent": "f2da4f90",
  "retired": "68235047091de0a0312c6bdd1b65a8c34d8a596b",
  "request": "ZX7_SUPER_VL_G1_WIRE_PLACEMENT_20261127",
  "authority": "Prior bounded owner consent, exact synthetic brief and grant profile, no private media or expanded grant, 48-turn Super VL",
  "status": "in_progress observed after native pinned editor build; no acceptance inferred; inspect final evidence without blind replay"
 }
}
```


## Preserved exact receipt coedit_host_observation_boundary_20261127

```json
{
 "parent": "013ef94d610b63078d39cd38878051367cb6f150",
 "source_blobs": {
  "studio_next/capability_mcp_session.py": "b4fa08d78eb0580cf85f43faa8126f8b1b49b5b6",
  "studio_next/native_creative_control.py": "eae2274264981af5565a8fdcce42d92e153ac2f8",
  "studio_next/test_native_revision_fence.py": "0018ff84670b529786e67d3829781fcd71e73ee7"
 },
 "reproduction": "Exact installed source (unchanged gateway/test base, controller 013ef94 blob verified). Actual production Python controller/gateway with source-shaped deterministic renderer: manual edit position 99 after model's timeline observation, before its selected set_clip_style write. Host-only full timeline preflight renewed model epoch and stale position 40 was committed. RED both single and combined routes. No actual human field claim.",
 "correction": "Separate host-only READ from model-visible gateway call, preserve same live admission, permissions, request identity, source lock and shared budget. Controller mechanical clip/placement preflight uses host-only route. No host-only write, revision promotion, hidden retries or novel grant. Fresh model-visible read remains required; canonical model-visible bootstrap/postwrite reconciliation unchanged.",
 "verification": "Both routes GREEN: stale write rejected before native dispatch, simulated human position 99 preserved, fresh model-selected replan position 100 committed once. Additional controls: no ungranted tools or writes via host-only route; host-only get_project/full timeline cannot mint or renew model revision. 288 affected tests, 284 pass, 4 missing-checkout file/import errors, zero assertion failures. Candidate hosted/native GUI acceptance still unverified.",
 "parent_ci": {
  "observed": {
   "in_progress": 2,
   "success": 26,
   "failure": 1
  },
  "physical_job_first": 140341368353,
  "first_failure": "Native Electron image-sequence regression log reached original defect reproduction then timed out (124); exact lifecycle predicate unknown.",
  "retry_job": 140343995262,
  "retry_failure": "Before GUI tests, Microsoft apt InRelease HTTP 403, exit 100. Separate infra failure; no further blind rerun.",
  "workflow": 45949362927,
  "remaining": [
   {
    "id": 45949362994,
    "name": "ZX7 MLT Editorial Native Research and Fidelity Gate",
    "status": "in_progress",
    "conclusion": null
   },
   {
    "id": 45949362965,
    "name": "ZX7 BODY — Installed Package, Desktop and Physical Crash Proof",
    "status": "in_progress",
    "conclusion": null
   },
   {
    "id": 45949362927,
    "name": "ZX7 BODY — Genuine Native Editor MCP A/V, Export and Visual Evidence",
    "status": "completed",
    "conclusion": "failure"
   }
  ],
  "terminal": {
   "success": 28,
   "failure": 1
  }
 },
 "scoped_g1_retest": {
  "run": 45950462408,
  "job": 140344855257,
  "parent": "013ef94d610b63078d39cd38878051367cb6f150",
  "trial": "e979730bb06ca9e8d7d50d3f689feabb0f2a9597",
  "retired": "8035aa15c424db5d7361a94172a76b15de85e931",
  "branch": "trial/g1-super-vl-indexed-recovery-20261127",
  "request": "ZX7_SUPER_VL_G1_INDEXED_RECOVERY_20261127",
  "scope": "2026-11-22 owner standing 48-turn synthetic-only G1 permission; exact prior Super VL model, indexed catalog and unchanged brief; test two integrated causal corrections. No private media, broader paid scope or replay. Trigger retired by forward commit restoring source tree. Actual inference step running at observation, not result.",
  "terminal": {
   "conclusion": "failure",
   "artifact": 15177080510,
   "zip_sha256": "2d509a766a1b20ff11fa93c11aaf2c0ca9a29951db9fe5d13d5e78b2b003c5f6",
   "zip_entries": 15,
   "crc_verified": true,
   "decisions": 7,
   "provider_reported_tokens": 56792,
   "model_wall_ms": 297095.356,
   "native_wall_ms": 369.79,
   "searches": 1,
   "write_acknowledgments": 3,
   "exports": 0,
   "saved": "One original six-second video clip; native/staged original hash ea0737ff253bdecd3d730701e6700b04ded8a024eed7715f561a76174f76084d matches; no imported/placed audio.",
   "events": "Turn 3 stale refused, turn 4 fresh get_project, turn 5 search, turn 6 add_asset_to_timeline error classified uncertain and halted.",
   "error_digest": "fdece17a19f0ad9ca8123912e3805daa7620565d17e71c38f824137a4e222a00",
   "diagnosis": "Exact digest of canonical wire list containing fixed placement_plan_unconfirmed BODY message (no timeline edit submitted). Wire/public revision-token digest mismatch reproduced against exact source. Actual raw receipt metadata absent from journal; underlying reason placement preview failed remains unresolved.",
   "independent_acceptance": false
  }
 },
 "next": "Integrate coedit and verified wire refusal correction after terminal parent gates; retain desktop failure; exact-head SDK/native/physical and genuine human acceptance still required."
}
```


## Preserved exact receipt wire_bound_bridge_refusal_20261127

```json
{
 "parent": "013ef94d610b63078d39cd38878051367cb6f150",
 "coedit_parent": "c2b75bd84107a2099301ada1676a937d9a5228c7",
 "source_blobs": {
  "studio_next/capability_gateway.py": "7e44a7900df27e48ed9dcf2ad7cf2abb1fb84640",
  "studio_next/capability_attempts.py": "113344a25313cfa7c7f7316b414a924d89622669",
  "studio_next/capability_mcp_session.py": "9b370bac2c7ab68bbcd84ce108bfeb80ae394bd4",
  "studio_next/native_editor_session.py": "5d62c23f5cfec852e1c1b00ce84ad3cc6798bbd6",
  "studio_next/studio_mcp.py": "58675290fcd37c889fe4739e8a2ecdc143c8787c",
  "studio_next/test_body_editor_mcp.py": "e95dbbee21f3699caf01ccbd76f5522b4f443a0f",
  "studio_next/test_native_revision_fence.py": "e74c5fd1ecc811a168c9c0bd3b028d23fb27d9e1",
  "studio_next/test_capability_attempts.py": "12747f59c6c7cbc8b740bd9af83d2c705ecbf2ab"
 },
 "installed_parent": {
  "run": 45949362965,
  "artifact": 15177330866,
  "zip_sha256": "42a30178998882537bd8579ee523b2b1438ec1f037a3032c46c7f6db20fd1cf9",
  "tests_run": 1784,
  "pass": 1754,
  "skip": 30,
  "failed": 0,
  "manifest_verified": 24,
  "physical_mp4_full_decode": 3,
  "exact_equal_tree": "abf2171f93b095e31775a4f73fcdafa4c9e0d846",
  "merge_test_commit": "678bdd5a2d1527f8a343acf87159305ac45372ac",
  "crc_verified": true,
  "local_wheel_source_hashes_verified": true,
  "hosted": {
   "success": 28,
   "failure": 1
  }
 },
 "reproduction": "Four assertion failures on original behavior: exact trusted wire refusal falsely uncertain in both routes, forged public-input receipts falsely accepted. Underlying preview reason not proven.",
 "correction": "Explicit trusted local editor source only; strict error and exact augmented wire digest, immutable expected input snapshot; gateway rebinds verified refusal to public input, preserves prior observed epoch; strips reserved untrusted metadata. Durable terminal host_rejected_no_native_write distinct from conflict/uncertainty; migrate V1/V2 without losing attempts, preserve no replay. No grant expansion, auto retry, or acceptance relaxation.",
 "verification": {
  "focused": "Seven refusal controls GREEN plus stale human edit after safe refusal; physical SQLite V2 migration and replay prevention GREEN.",
  "run": 325,
  "pass": 286,
  "skip": 36,
  "errors": 3,
  "assertion_failures": 0,
  "limitations": "Optional MCP SDK unavailable locally (36 skips including new real HTTP/SDK test); three missing checkout script imports. Hosted SDK and native evidence pending."
 },
 "next": "Verify exact-head CI and real SDK bridge; diagnose desktop physical test separately; continue critical-path genuine creation/revision/human coedit then matched routes/A-L independent acceptance. No repeat of spent trigger and no further inference before corrected evidence.",
 "independent_acceptance": false,
 "hosted_followup": {
  "observed": {
   "success": 25,
   "in_progress": 3,
   "failure": 1
  },
  "real_sdk": {
   "run": 45952719717,
   "job": 140352046550,
   "passed": [
    "test_cas_placement_preflight_receipt_survives_actual_sdk_gateway",
    "test_wire_bound_placement_refusal_is_not_an_uncertain_write",
    "test_controller_clip_style_preflight_cannot_refresh_stale_model_epoch",
    "test_revision_schema_migration_preserves_uncertain_and_confirmed_intents"
   ],
   "limits": "Real HTTP/MCP SDK bridge; source pin fixture. 346-test SDK group and 271-test gateway group completed; not actual human study."
  },
  "desktop": {
   "run": 45952719679,
   "job": 140352046121,
   "conclusion": "success",
   "previous_failed_parent": 45949362927
  },
  "research": {
   "run": 45952719864,
   "job": 140352046589,
   "conclusion": "failure",
   "detail": "17 of 18 live provider/language checks passed; Europe PMC unavailable or invalid JSON, underlying transport cause not logged. Existing same-URL timeout retry only, no blind rerun."
  },
  "running": [
   45952719857,
   45952719639,
   45952719866
  ]
 }
}
```


## 2026-11-27 — editable animated cubic path mask

{
 "scope": "Field D: existing editable visual graph path_mask primitive, animated cubic contours in original canvas pixels, straight closure, evenodd/nonzero fill, invert; multiply associated RGBA without flattening source. Not automatic segmentation/tracking or a professional UI.",
 "source_blobs": {
  "studio_next/body_visual_graph.py": "039a7ef29a76520ead6af1782028f1d5853f523e",
  "studio_next/body_visual_contract.py": "0a7fc79f5525b65da82606396030e04a7e17072f",
  "studio_next/body_integration.py": "ea625266c7cf88500ec6f52322c541bda484653a",
  "studio_next/test_body_path_mask.py": "8522842a4561baba794e7dd210201504e4cdf348"
 },
 "controls": "512 authored segments, 4096 flattened edges, finite +/-1e6 coordinate, 1/32-pixel cubic deviation bound, half-open scanline winding, 8x8 subpixel samples, combined frame work budget; explicit remap for unequal source size.",
 "red": "5 focused cases failed before new primitive existed.",
 "green": "26/26 affected local tests incl 6 new independent geometry, coverage, holes, animation and immutable PNG revision; actual RGBA MOV 8 distinct frames, 3-frame excerpt exact pixel-hash equality. Source/contract/test remote hashes equal tested local blobs.",
 "limitations": "Finite sampled edge coverage, bounded contour complexity, no feather-specific UI, automatic tracking or independent field acceptance. Combined hosted proof pending."
}

## 2026-11-27 — exact F/G integrated hosted and installed evidence

{
 "source": "66b4465baa1405197ff9c886b9e47c2e47d0e423",
 "tree": "931492ce7b8d67abe7f772fa72c76ad38213e422",
 "hosted": "29/29 success",
 "installed_run": 46007162992,
 "artifact": 15203156105,
 "sha256": "962a8777a6be7b71db77435d55f8dccaa948253a64f2401bdcd97206a62d81e6",
 "tested_merge": "0f07258bbfdadcc3b22b84fe8f0647ec8c5305dd",
 "tree_equal": true,
 "manifest": "24/24",
 "full_decodes": 3,
 "tests": {
  "total": 1800,
  "passed": 1769,
  "skipped": 31,
  "failed": 0
 }
}

## 2026-11-27 — terminal genuine G1 and integrated A/D/E failure audit

{
 "g1": {
  "run": 46007258095,
  "job": 140533444321,
  "source": "c29c135f96bf6d25658b3fd830245c907119ea2c",
  "parent": "f2da4f90",
  "retired": "68235047091de0a0312c6bdd1b65a8c34d8a596b",
  "request": "ZX7_SUPER_VL_G1_WIRE_PLACEMENT_20261127",
  "authority": "Prior bounded owner consent, exact synthetic brief and grant profile, no private media or expanded grant, 48-turn Super VL",
  "status": "failure: turn_budget_exhausted; one conforming native A/V export only; no reviewed distinct pair or professional acceptance; scoped trigger retired",
  "artifact": 15203767091,
  "sha256": "1c2c1180f3a4f1f9f858481613325cdcbba1bbefafe0d82ad31bfa56f7d7012d",
  "artifact_crc": "pass; 23 files",
  "decisions": 48,
  "searches": 21,
  "write_acks": 8,
  "usage_records": 46,
  "reported_tokens": 572800,
  "model_wall_ms": 1362433.837,
  "native_ms": 2756.901,
  "physical_export": {
   "count": 1,
   "sha256": "6cf4cfa9fb1ebfaad11edd5b74581443aefa2d8bd6bc694c83012ec10c5c6cb7",
   "video": "640x360 H264 24fps 144 frames",
   "audio": "AAC stereo 44100Hz; full decode; float PCM RMS 0.05555946 peak 0.12276136",
   "duration_s": 6
  },
  "source_custody": "Both staged and native original video/audio copies match source-ledger SHA256; saved native project SHA256 ab6924c0e7d350acb3b4e6fe6b857b2ff50e2786484d7cfb59248585ef46d73d; 3 clips, 2 video and 1 audio",
  "causal_observations": "Export turn23, combined verification turn25, timeline read26, searches27–36, frame37, numeric audio39, truncated decisions41/45, stale set_clip_style refusal43, fresh project44, redundant verification46, AV window47; no distinct revised export. Native safety refusal is not evidence of a controller defect. No new paid trial."
 },
 "integrated": {
  "source": "fbb95665280c58e8550d1f703b221a83a3b7e52a",
  "tree": "da6fece917fb55da5b89783b35234edac9c69978",
  "hosted": "25/29 success; 4 failure terminal",
  "common_failure": {
   "source_run": 46010679696,
   "installed_run": 46010679646,
   "mlt_run": 46010679250,
   "source_job": 140545074917,
   "installed_job": 140545076483,
   "mlt_job": 140545074025,
   "test": "test_cgi_texture_source_bytes_are_in_actual_material_fingerprint",
   "cause": "Legacy fixture fabricates x/y custody identifiers and arbitrary bytes; strict source custody correctly rejects it.",
   "red": "Exact local reproduction with body_materials and media_vault blobs matching remote; Unsafe media content digest.",
   "green": "16/16 local tests in test_cgi_tracking, test_body_materials and test_body_custody_graph; real PNG admission and digest change after explicit reattestation; reject mutated source under old receipt, forged IDs and withdrawn grant; physical planar A/V preserves native audio and color.",
   "test_blob": "826d5ab8561aade98e54990c37057b84d1beceba",
   "runtime_changed": false
  },
  "scene": {
   "run": 46010679491,
   "job": 140545307832,
   "status": "failed after successful Vite build, exact subsequent failure cause unresolved; do not label infrastructure or source defect without evidence"
  },
  "limits": "Candidate hosted verification pending. No new domain acceptance. Last fully green integrated parent remains 66b4465b."
 }
}

## 2026-11-27 — bounded working-checkpoint compaction

Previous full ledger and STATE retained at commit `573e952ccf1b9556fec8d56204ac749f30bc9cd8`. Exact archived receipts copied below; integrity failure #46023484152 retained, no guard relaxation. Live Europe PMC failure #46023484108 separately recorded.

{
 "latest_artifact_audit_20261126": {
  "head": "642565f1252f10caf65a1aa6f434672d25dcc3ba",
  "main": "716c226ab7cb24e5a662229d951bf7f8bc17a28f",
  "workflow_success": 29,
  "installed": {
   "run": 45740635402,
   "tests": 1736,
   "pass": 1706,
   "skip": 30,
   "artifact": 15082046544,
   "zip_sha256": "7b3182e3c55ba123c273e842f77e67e571f37a7946489d90e7ff0ffe5d9ea621",
   "manifest_pass": 24,
   "ffmpeg_decode_pass": 3
  },
  "mlt": {
   "run": 45740635652,
   "tests": 1736,
   "pass": 1735,
   "skip": 1
  },
  "electron": 45740635512,
  "browser": 45740635468,
  "model_jobs_skipped": [
   45740635638,
   45740635629
  ],
  "failed_real_runs": [
   {
    "run": 45738534918,
    "artifact": 15081186723,
    "zip_sha256": "3fa8af4f57d0e3a29ea8145bcfaf45c8427293e7eaefa30bb6c9ea68b652c43d",
    "write_acks": 7,
    "verified_exports": 0,
    "terminal": "native_render_snapshot_failed"
   },
   {
    "run": 45740294453,
    "artifact": 15081337311,
    "zip_sha256": "06cc972bfe825ce5d0fa280a2256593433f6e79ffe622d1303a402ddee286a11",
    "write_acks": 6,
    "verified_exports": 0,
    "terminal": "stale identity cleared project snapshot; turn 23 preview rejected",
    "correction": "Refuse source-bound image preview before dispatch without trusted project observation; model selects get_project; retain exact JPEG/identity validation.",
    "regression": "added; execution pending"
   }
  ],
  "acceptance": "G1/G1-HUMAN/G2/G3/G4 OPEN; no new cloud consent or independent acceptance"
 },
 "live_branch_ancestry_20261126": {
  "status": "ALL_REF_SOURCE_COMPARISON_NOT_PRODUCT_ACCEPTANCE",
  "baseline": "2b626445ecabd3a2837ac549a98ba9dcda94b96d",
  "run": 45737776415,
  "artifact": 15079562880,
  "zip_sha256": "9af70a197570059aadbe4f8f726bb1bb1bfca2c9c508ca4366495f521825a468",
  "refs": 472,
  "snapshot_refs": 459,
  "ancestor": 149,
  "identical": 1,
  "ahead_audit_only": 1,
  "diverged": 321,
  "unique_old_missing_code_sets": 17,
  "old_stack_branches_same_7_path_set": 48,
  "pr189_old_absent_names": 43,
  "no_bulk_merge": true,
  "evidence": "project-brain/EVIDENCE/2026-11-26-BRANCH-ANCESTRY-AND-NATIVE-SAVE-CUSTODY.md",
  "current_refs": 478,
  "additional_refs_compared": 6,
  "followup_source": "642565f1252f10caf65a1aa6f434672d25dcc3ba"
 },
 "g1_autosave_custody_20261126": {
  "status": "PHYSICAL_INSTALLED_PASS_GENUINE_MODEL_NOT_ACCEPTED",
  "real_run": 45735804964,
  "real_artifact": 15078888361,
  "zip_sha256": "97fde7d322af5b09e5338313e0964d2c271e65776a395947cce8a5a9fe2e83a2",
  "native_write_acks": 7,
  "first_export_ack": true,
  "verified_movie": false,
  "three_real_autosaves_same_non_clock_content_sha": "14ba70dcfe274ee70cb865485ebb2b01e5a98b4e409e7eb8feb09ab21a36e6f1",
  "exact_green": "94d33d6c5919b6af02c85783d0456b42455acb46",
  "red_green_run": 45739025215,
  "adjacent_pass": 185,
  "preservation": "Only 2 editor modified clocks may change between real model save and render; all creative and original media SHA stay equal; save witnesses separate from native rendered-revision registry.",
  "no_automatic_write_replay": true,
  "full_g1": "NOT_ACCEPTED",
  "physical_e2e_run": 45740635512
 },
 "g1_post_review_second_export_guard_20261125": {
  "source": "61cce9a78b44986e282102260c421d0df6204685",
  "real_negative_run": 45632856001,
  "real_negative_artifact": 15033430161,
  "source_event": "second export was model-selected and host-ACKed after verified first picture/audio, but before any post-review native content revision; capture did not attest a distinct saved native source",
  "scope": "Strict reviewed A/V, after first physically verified, frame-and-full-audio-observed export; reject second committed export until model-selected content revision (no automatic edit or write retry).",
  "red": "2998ddd22388d9882aa7b4e46d55754188cd20d6",
  "green": "61cce9a78b44986e282102260c421d0df6204685",
  "run": 45666106360,
  "red_failure": 1,
  "adjacent_green_tests": 193,
  "real_model_retest": "NOT_RUN",
  "professional_quality": "NOT_ACCEPTED"
 },
 "critical_path_coordination_20261127": {
  "baseline": "c02c2d0b6989eed4b0a9e7232ba79c2e18012221",
  "source_blobs": {
   "studio_next/native_render_evidence.py": "bf734855f314bf0d992ed11ba86bab6012f1ccda",
   "studio_next/native_creative_control.py": "aa6709dc61f8c83f904f747fa3050bce61ae4527",
   "studio_next/native_creative_audit.py": "72c7be04bf3562ef96531cd0c70fe7f589732e28",
   "studio_next/body_editor_mcp.py": "ecaaceea4883cde93724f68cd7812a6f7a9e0ee9",
   "studio_next/test_body_editor_mcp.py": "42beba2ac3c0fd655c715487f3605e5a013564de",
   "studio_next/test_native_creative_control.py": "56c1de9049586333b553bea8d867ede8622925c2"
  },
  "causal_gap": "Existing model-selected AV window delivered source-bound frames and numeric PCM but strict pair gate credited only separate frame/audio calls.",
  "matched_control": {
   "decision_turns": 10,
   "native_calls": 9
  },
  "matched_candidate": {
   "decision_turns": 8,
   "native_calls": 7
  },
  "scope": "Scripted identical evidence fixture only; 20% fewer decision turns, not measured neural speed/cost or artistic quality.",
  "red": "Combined full coverage exhausted budget on baseline; separate route passed.",
  "green": "Both routes accepted technical pair, partial/overstated coverage rejected; altered receipt values refused by auditor.",
  "local": {
   "eligible_tests": 201,
   "passed": 201,
   "limitations": "Broader runs had missing MCP SDK (3) and repository-only scripts (2); not full suite. Added real decoder MCP comparison awaiting CI."
  },
  "acceptance": {
   "professional": false,
   "genuine_model": false,
   "exact_source_ci": "29/29 workflows SUCCESS at f676146e7a95da42fd39eb62d72154e2bce1af54; actual model jobs skipped"
  },
  "guard": "Existing grants, model-selected action, frame separation, verified duration, actual PCM and hash binding; no semantic listening or approval inferred. No new provider spend.",
  "next": "Baseline physical parity passed. Qualify provider/model and run comparable genuine synthetic trial only within exact-source, one-use consent; no available dispatch action in current connector.",
  "physical_mcp_parity": {
   "run": 45894468630,
   "jobs": [
    140164828950,
    140164829134,
    140164829172
   ],
   "result": "SUCCESS on Python 3.13/3.12/3.11; real SDK + independent FFmpeg + source-bound negatives; not neural"
  }
 },
 "critical_path_timed_feedback_20261127": {
  "retained_in": "EVIDENCE/INDEX.md#retained-historical-timed-feedback-structured-receipt",
  "original_ledger_blob": "fdfef087c1d7603731d2e96fab969f04cbff7e34",
  "summary": "Source-bound timed picture readiness, original five failed workflows and fixture correction, full technical 29/29 on corrected baseline. Full historical record retained."
 },
 "critical_path_delivery_affordance_20261127": {
  "retained_in": "EVIDENCE/INDEX.md#retained-historical-delivery-affordance-receipt",
  "original_ledger_blob": "c823687f0d9e4b84341a5ebaf43a8eba2e6d53cd",
  "summary": "Delivery readiness: scripted 6→3 decisions, same native calls, exact hosted 29/29; genuine indexed and direct trials failed acceptance. Full original structured receipt retained."
 },
 "reused_archived_scope_20261127": {
  "research": "cea19dadc38cccb212e9d37331ca1869d200b724",
  "scheduler": "633348babde51ba037bf1917fe1f051bd2515aae",
  "source": "Existing exact 8 blobs; matching unchanged parent blobs, no reimplementation. Add 3 read-only public metadata providers and explicit source choice, preserve network/rights gates; truthful scheduler state label.",
  "local": "Scheduler RED assertion true vs false; GREEN 17/17. Research RED provider kwarg unsupported; exact four production + test blobs match. 63 affected tests: 58 pass, 4 SDK skips, 1 no-display error, targeted desktop Xvfb rerun passes (59 distinct passed). Real public endpoints/SDK and CI pending.",
  "acceptance": "candidate, not full public web, domain or release acceptance",
  "live_followup": {
   "run": 45937275501,
   "observed": "Cleveland success; NASA empty because all three live Apollo IDs have spaces; Europe PMC runner request failed, independent same-query HTTP 200 JSON returned; runner cause not proven.",
   "correction": "Allow bounded interior ASCII spaces in NASA ID and quote URL segment; reject path and control characters. Exact RED→GREEN; 71 run/67 pass/4 optional SDK skips.",
   "physical_oracle": "Four synthetic aligned, offset, sound-only, picture-only controls; known target detects brief red event missed by equal-count uniform samples; FFmpeg decoded PNG and audio bins verified; no neural or artistic acceptance.",
   "native_ci_negative": "45937275794 job 140303602801 Microsoft apt repository HTTP 403 before tests; not a source regression.",
   "acceptance": "Exact new head live verification pending.",
   "latest_live": {
    "run": 45937892821,
    "initial": "30/30 offline research; NASA live 3 reference leads; EPMC timeout",
    "diagnostic": 45938105014,
    "diagnostic_result": "Exact query HTTP 200 in 2.733s, 3 accepted records; p53 control timed out. Intermittent transport, not proven parser defect.",
    "retry": "SUCCESS attempt 2, unchanged source"
   },
   "repeated_transport": {
    "run": 45938988502,
    "job": 140308669885,
    "result": "Europe PMC failed again; earlier exact same query succeeded independently and on unchanged-source live retry.",
    "correction": "One additional same-URL public GET only for exact Europe PMC metadata endpoint on direct/wrapped TimeoutError; 10s socket timeout per attempt, no redirect/status/JSON/other provider/loopback retry.",
    "verification": "RED: recovery missing, attempts 1 instead of 2; GREEN direct/wrapped timeouts, persistent timeout terminal, other errors single attempt. 31 tests run/27 pass/4 local MCP skips. Real live CI pending."
   }
  }
 },
 "self_contained_source_custody_20261127": {
  "baseline": "4e2c4338841e77f601443cfc55f986c53437b183",
  "baseline_ci_observed": {
   "success": 27,
   "in_progress": 2
  },
  "red": "Actual HLS file containing only a separate TS reference accepted as MP4, MP3 and FLAC custody; delivery and timeline probes also accepted. All five assertions failed independently.",
  "fix": "Restrict self-contained video input demuxers to MOV/Matroska/WebM families and local file/pipe protocols at probe, full decode, timeline render and frame/audio readers; MP3/FLAC ingest uses matching demuxer. No remote/playlist imports inferred. Does not replace OS sandbox or solve all decoder vulnerabilities.",
  "green": "82/82 affected tests, real HLS refused before custody publication, no object/attestation, actual MP4/MOV/MKV/WebM/MP3/FLAC positive controls and extensionless video CAS.",
  "status": "local exact tested blob candidate; hosted verification pending",
  "followup_reference": {
   "red": "HLS within authorized reference directory decoded outside-root TS file",
   "green": "Shared demuxer restriction across reference probe, visual and audio decode; all 6 reference tests passed; no OS-sandbox claim."
  },
  "hosted_observed": {
   "source": "78d68dca27ff37fe077ce556c7fddae0430fd888",
   "counts": {
    "in_progress": 15,
    "success": 13,
    "failure": 1
   }
  },
  "followup_staged_ingest": {
   "baseline": "ec4af1176fc9cd91d18b5e0dd7ef1051b6784f9a",
   "red": "Exact SVG source replaced by same-sized invalid bytes immediately after genuine parser validation; old ingest attested the replacement digest.",
   "green": "Copy to private same-filesystem stage, check source FD stability, validate and hash the same staged bytes before no-replace CAS publication; rehash after validation, always clean stage. Reproduced race now retains validated original; replacement has no attestation.",
   "combined_tests": {
    "run": 92,
    "passed": 88,
    "skipped": 4,
    "failures": 0
   },
   "source_blob": "4a882a8205fc9911e2de8bb8ca51e552e46448f4",
   "test_blob": "efaf60371e81203ca93758566e4990f348f1f3d9",
   "limits": "Local regression; no broad OS sandbox or external adversary guarantee. Exact new hosted CI pending."
  }
 },
 "perception_and_exact_lookup_20261127": {
  "retained_in": "EVIDENCE/INDEX.md#retained-historical-perception-and-exact-lookup-structured-receipt",
  "original_ledger_blob": "566c8d86dd1097e88fa4e3d2f5686ea2c37c4701",
  "summary": "Visual calibration passed basic sampled/numeric tasks; raw audio pitch failed, speech calibration passed only short synthetic English. Exact lookup correction retained, no professional semantic acceptance."
 }
}

## 2026-11-27 — Field G selected audio program/standalone master audit candidate

{
 "parent": "f036a1552af2b6080344e4e840c5b6d35727c207",
 "code_blobs": {
  "studio_next/body_loudness.py": "bb6e38c7892fc643f8c1786d871ae38687f81a29",
  "studio_next/body_document_schemas.py": "6855129674f56b41b05141e149a15fda17502c55",
  "studio_next/body_integration.py": "55e14a4f22740bf0159c2cfc1d12e59a48f0066b",
  "studio_next/test_body_loudness.py": "974bcb3762a5e65fca6efe6a16c2b8cdebe0e294",
  "studio_next/test_body_shared_revision.py": "f6bd950cb001e2330f8250bbefd0c692cdecc39c"
 },
 "scope": "Read-only body.loudness explicitly selects one to eight audio stream ordinals, preserves default first-stream behavior and scalar contract, returns separately measured LUFS/LRA/true peak, actual decoded count/sample rate/channel count/language. WAV, FLAC and MP3 masters supported; no stem inference, semantic listening, normalization or professional acceptance.",
 "negative": "Prior first-track-only contract cannot express alternate selections or standalone audio; local RED confirmed edit_timeline decoder-policy change left new loudness cache revision unchanged.",
 "local_verification": "18/18 loudness/subtitles/materials/custody graph tests and 16/16 physical composite_mix tests. After cache dependency correction 11/11 shared-revision/loudness tests. Actual alternate AAC programs at 48k/44.1k with distinct gains and language tags, independent PCM sample count oracle, standalone PCM 57600 samples at 48k, FLAC and MP3 actual stereo decode counts, original SHA unchanged; invalid selection and withdrawn receipt refused. No hosted acceptance yet.",
 "parent_hosted_observed": "25 success, 1 failure, 3 in progress; native atomic range #46023936864 failed in pinned Electron build after Vite/JS checks; exact subcommand unproven. Do not cancel active parent verification.",
 "limits": "No private media/model use, no mix quality judgment, no calibrated professional acceptance. Existing source custody only; no expansion of grants."
}

## 2026-11-27 — G1 alternating capability search cycle

{
 "parent": "654c5b0275d87998d34a5181f5da35fd78f4cc82",
 "code_blobs": {
  "studio_next/native_creative_control.py": "11b3fc50aef57f244e55a7c7ffdbe4ab72462db0",
  "studio_next/test_native_creative_control.py": "d42fc0fa3cdd3cbad77454f445e5bfb7014b6478"
 },
 "actual_trial": {
  "run": 46007258095,
  "artifact": 15203767091,
  "searches": 21,
  "distinct_query_hashes": 13,
  "repeated_query_hash_turns": [
   10,
   14,
   27,
   30,
   34,
   35,
   36,
   40
  ],
  "reported_search_tokens": 271235,
  "reported_repeated_hash_search_tokens": 113438,
  "search_only_burst_turns": [
   27,
   36
  ],
  "reported_burst_tokens": 145163,
  "qualification": "Hash repetition across whole session does not prove redundancy after a native action; query limit not recorded in old journal. Token sums are observed usage, not projected savings."
 },
 "cause": "Previous controller only flags consecutive identical query+limit+catalog revision; alternating same queries within uninterrupted metadata-only streak evade signal. RED exact local test KeyError for missing feedback.",
 "correction": "Replace adjacent-only counter with bounded per-streak signature counts (max 128 decision turns); reset at non-search action, preserve exact query/limit/revision and grants, no automatic dispatch or artistic decision. Journal emits bounded repeat count telemetry, not acceptance.",
 "verification": {
  "targeted": "3/3 RED→GREEN alternating repeat, consecutive repeat and describe reset. No native calls, no invocation from empty result, journal structure valid.",
  "combined": {
   "run": 248,
   "passed": 241,
   "errors": 7,
   "failures": 0,
   "errors_due_to_missing_local_checkout_or_dependencies": [
    "scripts.run_native_model_trial",
    "engines/velorn/editor.example.json",
    "mcp"
   ],
   "scope": "Wheel-based local overlay, not full checkout. Hosted exact source verification pending."
  }
 },
 "limits": "No measured genuine model turn/token savings, no semantic/creative/release acceptance, no new live model trial or private egress."
}

## 2026-11-27 — parent installed artifact and fail-closed atomic range diagnostics

{
 "parent": "f036a1552af2b6080344e4e840c5b6d35727c207",
 "observed_matrix": {
  "success": 27,
  "failure": 1,
  "in_progress": 1
 },
 "installed": {
  "run": 46023937134,
  "job": 140590354038,
  "independent_ci_job": 140600975851,
  "artifact": 15212611150,
  "sha256": "ce8a9462762794d03f9651ff086df02f5e9a9ead276c9ea74a9c16913689657e",
  "local_crc_ok": true,
  "manifest_matched": 24,
  "manifest_total": 24,
  "local_full_decodes": 3,
  "tests_run": 1814,
  "tests_passed": 1782,
  "tests_skipped": 32,
  "tests_failed": 0,
  "tests_errors": 0,
  "merge_source": "85b8e91dcf778ed5d0528e735ec77afd8a58a438",
  "exact_tree": "5b8fbed418a02e746243f6a763ffeebda0996d86",
  "limits": "Installed technical proof, no independent professional acceptance."
 },
 "pending": {
  "run": 46023937016,
  "job": 140590479244,
  "step": "Run every existing and new studio application contract on this exact branch"
 },
 "atomic_range": {
  "failed_run": 46023936864,
  "failed_job": 140591531636,
  "prior_success_run": 46007163085,
  "prior_success_job": 140533459148,
  "observed": "Vite build succeeded; silent post-build checks exit 1; previous exact guard passed. No exact failed command/cause established.",
  "workflow_blob": "da5b964e6ebb1e349c50200e9e73e4050d6a5b00",
  "change": "Report missing index/helper, sandbox permission stage, actual version stdout, subprocess exit code and mismatch. Retain exact version and sandbox requirements; explicitly fail nonzero probe even if stdout matches.",
  "local_verification": "bash -n and six shell fixture cases (missing index/helper, chmod/chown-stage refusal, nonzero version command, wrong version, exact positive). Not real Electron proof.",
  "limits": "No root-cause resolution or guard weakening claimed. Require actual hosted retry with diagnostics and native physical proof."
 }
}

## 2026-11-27 — exact parent terminal matrix

{
 "source": "f036a1552af2b6080344e4e840c5b6d35727c207",
 "matrix": {
  "success": 28,
  "failure": 1,
  "in_progress": 0
 },
 "mlt": {
  "run": 46023937016,
  "job": 140590479244,
  "tests_run": 1814,
  "passed": 1812,
  "skipped": 2,
  "failed": 0,
  "additional_separate_test_runs": [
   52,
   26
  ],
  "result": "success"
 },
 "remaining_failure": {
  "run": 46023936864,
  "job": 140591531636,
  "stage": "post-Vite sandbox/version checks; exact failed subcommand unproven; diagnostic correction in candidate"
 },
 "candidate": "cd6858ec3989b498def8e121b3c95c69cfbeb72a",
 "decision": "Parent matrix terminal; integrate cumulative candidate via non-force expected-head update. No merge into main or independent acceptance."
}

## 2026-11-27 — integrated baseline and media-decision continuity

Exact previous mutable ledger: [4b6e0334](https://github.com/ZX7-Labs/Zx7-creative-studio-/blob/4b6e033419b516afdf407ca9c4120b647d7e9c2d/project-brain/EXECUTION_LEDGER.json), blob `d1024297f857229c442e6bc0060287b293d99fb9`; previous checkpoints preserved verbatim there.

{
 "verified_baseline": {
  "source": "4b6e033419b516afdf407ca9c4120b647d7e9c2d",
  "observed_date": "2026-11-27",
  "checks_observed": 29,
  "counts": {
   "success": 29
  },
  "merge_test_commit": "0d07189cac81399e34233649276450abe9e7558c",
  "exact_equal_tree": "19d6758f79ce08f6b653eb38b7cf5e07bd42e508",
  "actual_model_jobs_skipped": [
   140613310423,
   140614128627
  ],
  "installed": {
   "run": 46030660749,
   "job": 140613304824,
   "tests_run": 1819,
   "pass": 1787,
   "skip": 32,
   "failed": 0,
   "errors": 0,
   "independent_ci_job": 140622810383,
   "artifact": 15215895554,
   "zip_sha256": "f8a6810ba8a9b1dc12146c480a40cb6b3adbb9a555fb9afadfdfd9f185e8137a",
   "local_crc_ok": true,
   "manifest_verified": 24,
   "physical_mp4_full_decode": 3,
   "local_redownload_verified": true
  },
  "mlt": {
   "run": 46030660842,
   "job": 140613305267,
   "tests_run": 1819,
   "pass": 1817,
   "skip": 2,
   "failed": 0,
   "additional_separate_test_runs": [
    52,
    26
   ]
  },
  "atomic_range": {
   "run": 46030660837,
   "job": 140613651638,
   "physical_native_pass": true,
   "exact_electron_version": "45.2.3",
   "prior_failure_run": 46023936864,
   "prior_failure_root_cause": "Unknown exact failing post-Vite command; current diagnostics succeeded, no causal claim."
  },
  "creativity_release_accepted": false,
  "previous_exact_ledger_commit": "4b6e033419b516afdf407ca9c4120b647d7e9c2d",
  "previous_exact_ledger_blob": "d1024297f857229c442e6bc0060287b293d99fb9"
 },
 "new_candidate": {
  "baseline": "4b6e033419b516afdf407ca9c4120b647d7e9c2d",
  "actual_trial_run": 46007258095,
  "artifact": 15203767091,
  "observed": "Turn 25 combined A/V; turn 26 model chose get_timeline with 98-byte reason, journal retains only hash; turn 27–36 search burst. Exact controller consumed media on one decision and omitted model-authored rationale thereafter. Structural loss reproduced, causal contribution to neural failure unproven.",
  "correction": "One ephemeral bounded historical model-authored rationale per actual picture or audio input; at most 512 UTF-8 bytes per reason, explicit truncation, source/media digests and available observation timing. No new media dispatch, raw-media replay, persisted reason, new grant or semantic claim. Existing validators and acceptance gates unchanged.",
  "candidate_blobs": {
   "studio_next/native_creative_control.py": "66bad8d2e6e2f25062b9f3c3ed03ffadd8a518fd",
   "studio_next/test_native_creative_control.py": "522ca8ed31ef65482200341a19218c2d5aa77e1b",
   "studio_next/test_native_audio_model_input.py": "0a126ad580467a2f6eb97c0444dd13eab896aff4"
  },
  "local": {
   "red": 2,
   "green": 2,
   "run": 197,
   "pass": 192,
   "errors": 5,
   "assertion_failures": 0,
   "environment_errors": [
    "2 missing repository scripts imports",
    "3 missing mcp dependency"
   ],
   "scope": "Exact verified installed wheel overlay, no native or neural retest"
  },
  "next": "Require exact candidate source/native checks, then a bounded discriminating matched creative trial only if justified and under existing synthetic consent. Measure post-observation decisions, distinct physically verified revised export, original source custody and cost, not just memory availability. No acceptance change."
 }
}


## 27 Nov — sensory continuity trial, selected audio finish, precision source, derivative ancestry

Exact parent: [2fab105621d36a05958fc5f8cd06ea7e49e1584e](https://github.com/ZX7-Labs/Zx7-creative-studio-/blob/2fab105621d36a05958fc5f8cd06ea7e49e1584e/project-brain/EXECUTION_LEDGER.json), prior ledger blob `a9d629c80ff18f460ecbdf3d54d01b239a97ac61`. Local code blobs match exact tested files. Synthetic rights reproduction: create 4x4 RGBA PNG (75,143,215,255), ingest as owner_upload; native visual source node and expression photo_r*.5 / photo_g / photo_b, rendered PNG; dependent body.asset_vault uses $node_output. Withdraw original grant, inspect original refused; checkout derived grant to fresh file succeeds. No legal conclusion. Full observation:

```json
{
  "parent": {
    "commit": "2fab105621d36a05958fc5f8cd06ea7e49e1584e",
    "tree": "39444fc733f37fddb7bff12460c0a4dee2ef3480",
    "matrix_at_observation": {
      "in_progress": 2,
      "success": 27
    },
    "remaining": [
      {
        "id": 46044219985,
        "name": "ZX7 BODY — Installed Package, Desktop and Physical Crash Proof"
      },
      {
        "id": 46044220019,
        "name": "ZX7 MLT Editorial Native Research and Fidelity Gate"
      }
    ],
    "note": "Previous exact 29/29 baseline remains separately verified. Do not cancel parent MLT full run before it becomes terminal."
  },
  "trial": {
    "run_id": 46045586986,
    "job_id": 140663907085,
    "status": "in_progress",
    "conclusion": null,
    "source": "4719db96d6230c186064b4739d94e9be08e97fc0",
    "trigger_retired_at": "87df7e5be744b72b08fdbbe41dc12897c678fdc9",
    "request": "ZX7_SUPER_VL_G1_SENSORY_CONTINUITY_20261127",
    "model": "nvidia/nemotron-3.5-super-vl-120b-a12b",
    "same_brief_grants_source_sampling": true,
    "synthetic_only": true,
    "raw_audio_upload": false,
    "turn_ceiling": 48,
    "baseline_run": 46007258095,
    "hypothesis": "Matched cumulative search-cycle and sensory-rationale correction: post-observation search/decision counts, original custody, distinct revised physical export and costs. Not isolated causal attribution or semantic listening/professional acceptance. No retry; inspect terminal actual artifacts."
  },
  "audio": {
    "observed": "Native audio-only finishing previously mapped only first video/audio and reencoded picture as 8-bit yuv420p. Real multitrack test RED. AAC reencode extended sample clock; loudnorm shifted timestamps; integer sample-index retime after verifying continuous zero-origin source fixes these without silently rebasing gaps.",
    "correction": "Explicit audio_stream_index required with multiple programs. Existing film_finish, sealed CAS, select one audio stream in MP4; stream-copy all untouched video/audio/subtitle packets; shared physical proof extracted from subtitle delivery. Selected continuous audio trim/aresample and exact integer sample timebase, verify original logical and padded decoded sample counts and independent loudness before/after. Refuse unsupported clocks, other stream types, chapters/attachments, high precision/HDR or multitrack picture finishing rather than silently lose fidelity.",
    "physical": "Actual 160x96 24000/1001 10-bit BT2020/PQ-tagged H264, English 48k + Hindi 44.1k mono AAC and mov_text. Exact untouched stream packet digests, timestamps and independent decoded A/V; original SHA unchanged. Selected gain -6 dB checked RMS, normalization -23 LUFS ±1 fixture; 132300 logical/133120 padded decoded samples. Ambiguous/nonexistent selection, gap/overlap, unsafe picture finishing refused without publication.",
    "tests": {
      "finishing": "7/7",
      "neighboring": "48/48",
      "revision": "16/16",
      "combined_with_visual": "44/44 (overlapping tests, not additive)"
    },
    "limits": "MP4 targeted, not arbitrary container/stream/metadata/clock, formal general loudness compliance, professional mix, stems, calibrated HDR or semantic acceptance. Hosted candidate pending."
  },
  "visual": {
    "observed": "Original high-depth PNG explicitly refused before PIL conversion; RED actual 16-bit image.",
    "correction": "Native FFmpeg rgba64le decode into float32 with explicit sRGB declaration, bounded PNG chunk/metadata scan, exact byte length and existing linear transfer/associated alpha. Reject conflicting gamma/chromaticities, cICP/ICC/HDR metadata, duplicate/bad bounded chunks.",
    "physical": "Independent actual RGBA16 source-codeword and float transfer oracle, adjacent one-codeword difference preserved through authored graph math and physical edited PNG; source SHA unchanged; conflicting gAMA and cICP rejected. Separate direct native decoder probe grayscale, RGB, grayscale+alpha, RGBA and tRNS exact.",
    "tests": "33 run, 29 pass, 4 skipped (local OpenEXR unavailable); combined 44/44 pass including sound finishing and shared revision",
    "limits": "Only explicitly declared sRGB-compatible 16-bit PNG input; no arbitrary color profile or wide gamut; existing SDR PNG/MOV delivery remains 8-bit; no new EXR-file or professional acceptance. Hosted candidate pending."
  },
  "provenance": {
    "observed": "Actual local synthetic 4x4 owner PNG -> body.visual_graph expression photo_r*.5 -> body.asset_vault durable producer DAG all_tool_results_verified; derived bytes distinct, attestation generated_original/trusted_renderer with source_id only output SHA. After withdrawal of exact original attestation, original inspect refused but a fresh derived checkout succeeded.",
    "source_sha": "6e722263e450ddca6c7af5f708440fc9622a09290b463b3f634a400b54710b0c",
    "derived_attestation": "35ddd2849ceb76a73278bbe837525bacc74e336e40b8d7c28177078df8e18d0a",
    "scope": "Missing explicit ancestor-grant provenance and dependency enforcement; not proof of unlawful use or revocation of independently granted derivative rights. Preserve history and independent owner grants. Require host-derived dependency receipts, versioned migration, exact ancestor policy and race/restart tests before broad rights propagation; no guessed legal semantics or claim of full withdrawal."
  },
  "blobs": {
    "studio_next/film_finishing.py": "c94103c669c8b061b1c4909a0cdf08833b3abe74",
    "studio_next/body_stream_custody.py": "bfb49bc313d2a3b0b1bf1ccb36f413502c8a692b",
    "studio_next/body_subtitles.py": "d3370f473f7edb0c80b91476752cafa4761569b1",
    "studio_next/body_document_schemas.py": "57136be91b9211a1dff48119d67c65a963badb79",
    "studio_next/body_integration.py": "0d4f24d953fb9ec6e7ef4a2563cd0051ca30af77",
    "studio_next/test_film_finishing.py": "ff221ab70593c35d0c06068c069fe566cc0b4df0",
    "studio_next/body_visual_render.py": "38beba98b37d2be69ea8ba4358b8de10679025cd",
    "studio_next/body_visual_contract.py": "9ca9ab93cf56a3ad7dd1768dd6c26cc22ba7a166",
    "studio_next/test_body_visual_graph.py": "47de2d37bde8d7f1d42a0e39becf64bd0afb31ea"
  }
}
```


### Continuity exact installed artifact audit and fresh integration overlay

```json
{
  "source_commit": "2fab105621d36a05958fc5f8cd06ea7e49e1584e",
  "tested_merge": "809c304d2ecbfce490805d0bfcf78bf9a958e345",
  "matching_tree": "39444fc733f37fddb7bff12460c0a4dee2ef3480",
  "run": 46044219985,
  "artifact": 15222496646,
  "sha256": "80f7e6b52b76c4cae872dede32c58b57d0faed7ee86cea9bd8b81c90386d0de1",
  "tests_run": 1821,
  "passed": 1789,
  "skipped": 32,
  "failed": 0,
  "errors": 0,
  "independent_artifact_checks": "ZIP SHA/CRC, 24/24 manifest hashes/sizes, 3/3 full physical MP4 A/V decodes, all three sensory-continuity source/test wheel Git blob IDs exact. No genuine model or independent artistic acceptance.",
  "matrix": {
    "success": 28,
    "in_progress": 1
  },
  "mlt_run": 46044220019,
  "fresh_candidate_overlay": "Exact installed wheel from this run with nine candidate source/test blobs; 70 run, 66 pass, four optional OpenEXR skipped, exit 0. No fresh hosted or EXR acceptance."
}
```
Prior ancestry receipt `source_sha` field refers to **derived output** SHA, not original input SHA; corrected key in ledger. Prior complete receipt retained at `33b737021bb0900535bf9419949ebd9806879cac`.


### Continuity terminal exact parent matrix

`2fab105621d36a05958fc5f8cd06ea7e49e1584e`: 29/29 hosted workflow success. MLT [#46044220019](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/46044220019) job 140659308916 logs verified checked-out merge `809c304d2ecbfce490805d0bfcf78bf9a958e345` with exact parent tree; 52 and 26 preliminary tests, full 1821 tests / 1819 pass / 2 skip. No neural/creative acceptance. Safe fast-forward to independently locally verified physical-media candidate, no active parent CI cancelled. G1 matched trial #46045586986 status in_progress at observation.


## 28 Nov — terminal physical media integration, matched G1 negative and visual ancestor rights

Previous exact records at [76cc6e01ea03f247d50ef6b8dba92128c4b56d90](https://github.com/ZX7-Labs/Zx7-creative-studio-/blob/76cc6e01ea03f247d50ef6b8dba92128c4b56d90/project-brain/EXECUTION_LEDGER.json), blob `9a0659096ce43d95bd0a57182383270c01dc29ca`. Candidate exact code blobs match locally tested bytes. No acceptance gate changed.

```json
{
  "ci": {
    "source": "76cc6e01ea03f247d50ef6b8dba92128c4b56d90",
    "merge_test_commit": "c924af406e4cf6550a5c49fcfbe19b982afee3d4",
    "exact_equal_tree": "14ae19e13ccc568811e64ac05b126991bf49213e",
    "observed_date": "2026-11-28",
    "checks_observed": 29,
    "counts": {
      "success": 28,
      "failure": 1
    },
    "actual_model_jobs_skipped": [
      140669097002,
      140669281482
    ],
    "installed": {
      "run": 46047138772,
      "job": 140669096382,
      "independent_ci_job": 140675692496,
      "tests_run": 1823,
      "pass": 1791,
      "skip": 32,
      "failed": 0,
      "errors": 0,
      "artifact": 15223537158,
      "zip_sha256": "b56b21ed0b196587ffb56f73348c1af71a53aed004faee05b4de9f2119b87f02",
      "local_crc_ok": true,
      "manifest_verified": 24,
      "physical_mp4_full_decode": 3,
      "local_redownload_verified": true
    },
    "mlt": {
      "run": 46047138653,
      "job": 140669095900,
      "tests_run": 1823,
      "pass": 1821,
      "skip": 2,
      "failed": 0,
      "additional_separate_test_runs": [
        52,
        26
      ],
      "new_audio_finish_and_png16_tests_executed": true
    },
    "research": {
      "run": 46047138534,
      "job": 140669095015,
      "result": "FAILED",
      "failure": "Europe PMC unavailable or invalid JSON, elapsed ~20.8s; precise underlying transport/JSON cause unproven. Crossref, Openverse, Poly Haven, museum, NASA, eight Wikipedia languages, SiteMatrix 347 editions succeeded; Commons video returned zero leads.",
      "decision": "Keep failure, no weakened acceptance or blind rerun."
    },
    "creativity_release_accepted": false,
    "previous_exact_ledger_commit": "76cc6e01ea03f247d50ef6b8dba92128c4b56d90",
    "previous_exact_ledger_blob": "9a0659096ce43d95bd0a57182383270c01dc29ca"
  },
  "trial": {
    "run": 46045586986,
    "job": 140663907085,
    "source": "4719db96d6230c186064b4739d94e9be08e97fc0",
    "retired": "87df7e5be744b72b08fdbbe41dc12897c678fdc9",
    "baseline_run": 46007258095,
    "result": "FAILED_TURN_BUDGET_EXHAUSTED",
    "artifact": 15223750481,
    "zip_sha256": "091c9515d2b98b040d926ce0bac643030ae9874d47dd0c0f6321b4ac3f1cf350",
    "local_crc_ok": true,
    "archive_entries": 24,
    "turns": 48,
    "searches": 6,
    "write_acks": 13,
    "usage_records": 48,
    "reported_total_tokens": 614460,
    "model_wall_ms": 1197586.947,
    "first_export_turn": 12,
    "second_export_turn": 20,
    "previous": {
      "searches": 21,
      "tokens": 572800,
      "first_export_turn": 23,
      "export_count": 1,
      "model_wall_ms": 1362433.837
    },
    "physical": {
      "distinct_exports": 2,
      "distinct_picture_sequences": 2,
      "profile": "640x360 H264 24fps, 144 frames each; 6s synthetic A/V",
      "outputs": [
        "fe0eaf543c1d558412ed7bb51c8a7fa11268b0d08b5ebf3372600fbccb540d78",
        "46779dea997232807edc2fdac9d002cc8d8ea0216afd0f18d1bef8803efca37d"
      ],
      "local_rgb_hashes": [
        "9f3f959329525c3e036bc9258e39d58f61c818b9c65cbe439fe45514dcd242cd",
        "f40d0a607ab56b49770c9fc43413830535e505a8710d061d9fb97e77c2985311"
      ],
      "local_pcm_s16le_hash": "4762b126e870a82caa75aa4549f5903f2a46b507a4d06f1f0a0e637aa0ececa1",
      "audio_identical": true,
      "original_video_audio_staged_and_native_sha_match": true,
      "final_project_sha256": "9929d80c51c1ffd144a04c7e368f927b9667b0127cd9e6ca846985da96e6b619",
      "saved_clips": 4,
      "reviewed_native_render_pair": null,
      "reviewed_native_av_pair": null,
      "third_export_ack_turn": 47,
      "third_export_not_retained_or_verified": true
    },
    "refusals": {
      "stale_placement": 3,
      "output_exists": 7,
      "export_delivery_mismatch": 2,
      "export_target_enum": 1
    },
    "observations": "Both exports observed at 0,2,4s + full numeric audio 0–6s (turns 14/23), then additional video layer, no actual sound edit; saved audio gainDb 0, fadeIn/out 0. Later video clip scaleX/Y 1.6 and opacity 1; no inferred intended units. Final ACK at turn47 not a physical third export. Fewer searches/earlier distinct visual result, higher reported tokens, no isolated causal claim. No accepted pair or semantic hearing.",
    "next": "Isolate deterministic destination/profile coordination (existing feedback did not prevent repeated refusals); preserve model's choice to export and all native no-overwrite/authority checks. Inspect render source identity and intentional sound revision; no blind repeated paid full trial."
  },
  "correction": {
    "baseline": "76cc6e01ea03f247d50ef6b8dba92128c4b56d90",
    "blobs": {
      "studio_next/media_vault.py": "c24401f245afa239d75d0e6159216b1305ee767f",
      "studio_next/body_visual_render.py": "2eb8c83a3b8951931a87404ac7b566c0ee0036ab",
      "studio_next/body_publication.py": "467ef353f613ec06315a0745054c92697d2eaea4",
      "studio_next/body_integration.py": "3d5967d0af6fd534f9c5cc82a7347534de19bd94",
      "studio_next/test_body_derivative_rights.py": "b3e4b5f6573f777861ac859365afbe5205f836e5"
    },
    "red": "Two actual native visual derivative tests failed: fresh descendant checkout permitted after source withdrawal and at checkout link boundary.",
    "correction": "Real sealed visual graph records exact source attestation pairs from the renderer; verified physical output hash binds metadata, publication schema 2 persists/reconstructs same provenance on recovery. Vault optional lineage commitment extends exact grant identity and atomically stores ancestry; verify all transitive grant hashes/withdrawals inside read snapshot and checkout/ingest writer transaction. Bounded 1024 parents, 4096 nodes, 16384 edges. Independent grants preserve original hashes; lost new lineage row fails closed.",
    "local": {
      "initial_suite": 63,
      "final_run": 81,
      "passed": 77,
      "skipped": 4,
      "failures": 0,
      "errors": 0,
      "scope": "Exact 76cc6e01 installed wheel overlay, actual real PNG graph and two generations, source/derivative bytes preserved, independent grant, restart, checkout-boundary withdrawal, interrupted post-publication settlement without rerender, deleted lineage row, existing real Inkscape process-death tests, physical edit and custody. Four missing local OpenEXR tests skipped."
    },
    "limits": "Only visual graph producer now emits exact lineage; other trusted producer routes and historical unbound generated grants still require reconciliation. No raw-path recall, old backup update, historical deletion, claim of legal rights or broad revocation. Existing graph source revision policy remains; old unbound visual results may require new render with new path to issue lineage-bound grant. Hosted candidate pending."
  }
}
```


## 28 Nov — current reviewed comparison, exact G1 prefix evidence

{
  "baseline": "d6db538822bc0bda461b5a7104ae3a50dcda7772",
  "real_run": 46045586986,
  "artifact": 15223750481,
  "artifact_sha256": "091c9515d2b98b040d926ce0bac643030ae9874d47dd0c0f6321b4ac3f1cf350",
  "replayed_actual_journal": {
    "pair_qualifying_sequence": 73,
    "turn": 23,
    "matched_picture_seconds": [
      0,
      2,
      4
    ],
    "sampled_picture_changed": true,
    "comparable_audio_window_seconds": [
      0,
      6
    ],
    "decoded_audio_changed": false,
    "invalidated_sequence": 91,
    "invalidated_turn": 32,
    "invalidating_tool": "add_asset_to_timeline",
    "terminal_pair": null,
    "terminal_status": "turn_budget_exhausted"
  },
  "correction": "Exact script evaluator allows changed picture OR changed audio, not both; still requires matching source/render custody, audible conforming soundtrack, current evidence and model finish. Historical pair qualified technically at turn 23 then invalidated. No terminal or semantic/artistic acceptance. Expose current matching observation facts to model from existing invalidation-aware comparator, without action selection, automatic finish, proof relaxation, or invented meaning.",
  "blobs": {
    "studio_next/native_render_evidence.py": "b24058c46bb8a4e1d64cd9aebbab9147a32c646c",
    "studio_next/native_creative_control.py": "36c19c5234bb2e00369fe5dc74953a184efd1497",
    "studio_next/test_native_render_evidence.py": "82d3b505c42b8a4561777dd202ac55af45624aa9",
    "studio_next/test_native_creative_control.py": "8c6193ddb4ac6eb065de68b55162ffd80dce8778"
  },
  "tests": {
    "red": "missing comparison API",
    "focused": 13,
    "full_attempt": 172,
    "passed": 170,
    "environment_errors": 2,
    "environment_error": "installed wheel lacks checkout-only scripts.run_native_model_trial",
    "filtered_rerun": "170/170 pass, two named repository-script tests excluded only in local wheel overlay",
    "actual_journal_replay": "qualifying comparison sequence 73, null at 91, terminal null"
  },
  "limits": "No paid replay; no causal proof of autonomous improvement; repeated export destination/profile refusal remains; need exact hosted tests before integration and genuine qualified completion followed by independent assessment.",
  "parent_hosted_observed": {
    "success": 17,
    "in_progress": 12,
    "research_live": "success",
    "no_failures_observed": true
  }
}


## 28 Nov — independently verified derivative installation and owner export readiness candidate

```json
{
  "receipt": {
    "baseline": "d6db538822bc0bda461b5a7104ae3a50dcda7772",
    "tested_merge": "42a0ea1977d2da66848d02f087d5b2e1f5128eab",
    "exact_tree": "60ccc5e6436c33fa682afa39e1a96b457068bc05",
    "installed_run": 46101251651,
    "jobs": [
      140843964834,
      140848194870
    ],
    "artifact": 15246172402,
    "sha256": "292500ed737182e4426d0b18a9f93cdc659e42406f63f777d8a89e40414ae07a",
    "tests": {
      "run": 1827,
      "pass": 1795,
      "skip": 32,
      "failures": 0,
      "errors": 0
    },
    "verification": "All four new physical lineage tests executed; independently downloaded exact ZIP, CRC, 24 manifest entries, 5 changed wheel blobs, 3 complete FFmpeg physical media decodes; merge tree equal. No legal/artistic acceptance.",
    "hosted_observed": {
      "success": 28,
      "in_progress": 1,
      "mlt_run": 46101251636,
      "research_success": true
    }
  },
  "data": {
    "baseline": "3132f855cb907713a5fa37839cf95202cbbc7378",
    "real_failed_trial": 46045586986,
    "causal_target": "7 existing-output refusals, 2 delivery mismatch, 1 target enum. Previous feedback was reactive; no confirmed single neural root cause.",
    "correction": "Explicit owner-scoped H264 project-size candidate only after source-bound model-selected save and only if export is actually selectable and existing post-review revision gate allows it. Exact current export schema and scoped fresh unused path, no file reservation or implicit trim. Host-only granted check_export_readiness, exact projection of options and strict owner profile match, cached per save/options; current native receipt must match before offering. Bounded mismatch feedback, no model observation epoch advancement. Actual model still chooses and submits args; bridge readiness, grants, no-overwrite and save/capture/physical proof unchanged. Candidate retired on any apply submission even before file appears; no auto-dispatch or replay. H265 and unknown project-size routes receive no candidate.",
    "blobs": {
      "studio_next/body_editor_policy.py": "a2d626b9b2e569d1d165d3cf785c0852dc9102bb",
      "studio_next/native_editor_session.py": "1dfa413341a6b227411fdc88efb5cf60dbcdbfa7",
      "studio_next/native_creative_control.py": "85ed48198d15153b8139690fadeba94e19eed6b0",
      "studio_next/native_creative_audit.py": "e25bf53c10a41d0883816abba9e95a50de8c99a2",
      "studio_next/test_body_editor_policy.py": "004d22adeee3e551524204accd8bd9cf0dc96e1c",
      "studio_next/test_native_creative_control.py": "686147931086d12fee717d5ed6b1c040b4ffa471"
    },
    "tests": {
      "red": "missing path offer API, missing controller option, and readiness fact false; independently confirmed RED before correction",
      "focused": "2/2 passed; actual filesystem collision/symlink, missing grants/unsupported profile/schema, native mock readiness matching and wrong 1920px, stable one-read offer, exact chosen arguments, no unselected write, journal rejection of altered read-role",
      "related": {
        "total_attempted": 297,
        "passed": 258,
        "skipped": 36,
        "import_errors": 3,
        "failed_assertions": 0,
        "filtered_local_rerun": 294,
        "remaining_errors": 0
      },
      "environment": "installed wheel-only local overlay, three checkout-only scripts.run_native_model_trial imports unavailable and 36 official MCP optional tests skipped"
    },
    "limits": "Local scripted host coordination evidence, not genuine model capability or real native readiness on current candidate. Candidate optional and may be ignored. No new provider run. Existing filesystem race limits remain; offer does not reserve path or change existing no-overwrite enforcement. No broad H265 support claimed. Exact hosted matrix pending."
  }
}
```


## 28 Nov — derivative parent terminal 29/29; candidate integration

```json
{
  "source": "d6db538822bc0bda461b5a7104ae3a50dcda7772",
  "tree": "60ccc5e6436c33fa682afa39e1a96b457068bc05",
  "tested_merge": "42a0ea1977d2da66848d02f087d5b2e1f5128eab",
  "workflows": {
    "success": 29
  },
  "mlt": {
    "run": 46101251636,
    "job": 140843964765,
    "tests": 1827,
    "pass": 1825,
    "skip": 2,
    "fail": 0,
    "preliminary": [
      52,
      26
    ],
    "four_lineage_tests_passed": true
  },
  "installed": {
    "baseline": "d6db538822bc0bda461b5a7104ae3a50dcda7772",
    "tested_merge": "42a0ea1977d2da66848d02f087d5b2e1f5128eab",
    "exact_tree": "60ccc5e6436c33fa682afa39e1a96b457068bc05",
    "installed_run": 46101251651,
    "jobs": [
      140843964834,
      140848194870
    ],
    "artifact": 15246172402,
    "sha256": "292500ed737182e4426d0b18a9f93cdc659e42406f63f777d8a89e40414ae07a",
    "tests": {
      "run": 1827,
      "pass": 1795,
      "skip": 32,
      "failures": 0,
      "errors": 0
    },
    "verification": "All four new physical lineage tests executed; independently downloaded exact ZIP, CRC, 24 manifest entries, 5 changed wheel blobs, 3 complete FFmpeg physical media decodes; merge tree equal. No legal/artistic acceptance.",
    "hosted_observed": {
      "success": 29,
      "mlt_run": 46101251636,
      "research_success": true
    }
  },
  "scope": "technical only; not actual model or professional acceptance"
}
```


## 28 Nov — exact edit, finishing and matte derivative grants; mutable matte decoder defect

```json
{
  "baseline": "1e0123bc84d8825c65028240a2b0b41448f77df1",
  "local_source": "Installed wheel from fully verified d6db5388, exact changed physical modules identical on current canonical source",
  "blobs": {
    "studio_next/body_owned_edit.py": "77dc62dd8e811dd368b1001eb442e9a494a0181d",
    "studio_next/film_finishing.py": "f70d74823745da7f7817749745dba2739265786f",
    "studio_next/composite_mix.py": "2584ff1ad96da32c524271122692402fcb12e9f5",
    "studio_next/body_integration.py": "61de4e2e297ef7452cb9f216c7534851ff69b37f",
    "studio_next/test_body_custody_graph.py": "f692dd0e84a42ec792509cf859f947c1735f4203",
    "studio_next/test_composite_mix.py": "6a437f08f6dc6bdfe582b33b90487b0c2592c33f",
    "studio_next/test_film_finishing.py": "b27d00fa2e5c151ae917ec7c5ec8039e136dd684",
    "studio_next/test_body_integration.py": "b82fe823982db3dec6696a852481a67f5e0fa88e"
  },
  "red": [
    "Actual two-owner video edit grant lacked source_attestations.",
    "Actual matte input path in FFmpeg argv remained mutable workspace path; during real encode modified matte and restored before post-render checks. The discriminator tested kind==video instead of video_layers in sealing and final re-admission."
  ],
  "correction": "Extend existing exact source-attestation publication/recovery path to body.render_edit_owned, body.composite_mix and body.film_finish, using real renderer output SHA and exact admitted clip/layer/matte/source grants. Fix compositor matte discriminator at both private CAS sealing and commit-side re-admission. Shared canonicalization, no new custody subsystem or inferred ownership. Preserve independent grants and historical outputs.",
  "physical": "Actual two original MP4 edit and second-generation explicit picture grade/sound gain finishing; exact ancestor pairs, restart reuse, withdraw one source then block both dependent checkouts, unaffected source accessible. Actual original RGBA red picture and white matte, mutate workspace mask to black during FFmpeg then restore; all decoder paths private sealed, decoded output still red; exact matte grant and derivative checkout refusal after withdrawal. Existing selected-program audio-only finishing test now checks exact source receipt.",
  "tests": {
    "focused_red": 2,
    "focused_green": 2,
    "related_initial": {
      "run": 108,
      "pass": 106,
      "fail": 1,
      "import_error": 1
    },
    "fixture_correction": "Prior mock physical-dimension verifier fixture omitted now-required source_attestations; explicitly verify missing field rejection as well as unchanged physical mismatch checks.",
    "related_rerun": {
      "run": 107,
      "pass": 107,
      "fail": 0,
      "error": 0,
      "skip": 0
    },
    "environment": "One checkout-only scripts.research_audio_clock import unavailable in installed wheel; no test disabled in repository. Full hosted exact source required."
  },
  "discovered_boundary": {
    "adapter": "Legacy fit/fill body.render_edit_owned two 0.6s inputs at authored 24fps",
    "actual": "28 frames, r_frame_rate=120/1, time_base=1/1000000, duration_ts=1141666, avg_frame_rate=14000000/570833. Audio-only copy/reencode on local FFmpeg 7.1.5 changes unselected video duration_ts to 1182440 and avg_frame_rate to 100000/4223 while inspected packet timestamps match. Exact unchanged-stream verifier refuses, no accepted output. Separate picture+sound finish supported and verified; do not silently relax packet/timing proof.",
    "next": "Resolve native VFR/mux timing via separate physical contract; legacy fit/fill is not frame-exact editorial. Do not force CFR by dropping frames."
  },
  "limits": "Visual plus three more producer paths only; CGI, planar, ACES, EXR, motion and historical unbound grants still need exact lineage reconciliation. No independent legal or creative approval, old-backup recall, or global raw-path revocation. Hosted candidate pending."
}
```
