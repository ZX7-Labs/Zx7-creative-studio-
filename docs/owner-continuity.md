# ZX7 BODY — owner continuity and evidence ledger

**Evidence cutoff:** 2026-11-06. This is a durable handoff, not a claim that ZX7 is finished. Prefer live `main`, exact commit and CI evidence over any status in this document. All dates and observations below refer to specific checked runs.

## Product and acceptance boundary

ZX7 Creative Studio is an **open-source, local-first, swappable-brain, multi-capability creative BODY**, not a one-off AI video editor. An independent model creates artistic decisions; the BODY owns installed original OSS tools, schema and grants, physical source custody, immutable plans and revisions, crash recovery, independent native state observations, editable project save/reopen and verified exports. Video editing is the first exercised end-to-end capability, **not** a license to bake video assumptions into universal host contracts. Future graphics, sound, animation, 3D and other installed engines should reuse those contracts.

Passing Python tests or an exporter check is **not** artistic approval. Each claimed capability needs a genuinely model-chosen edit, independent observation, a second model-chosen revision based on that observation, physically decoded output, reopened editable native source, permission/license checks, and an explicit quality review of actual content. Do not silently replace a native editor with a scripted substitute or label synthetic fixtures as real creative evidence.

## Confirmed mainline progress

These are merged production contracts, not experimental feature claims. Before a new session starts, **verify the actual `main` HEAD and merged PRs again**.

| Merged work | Source of truth | What it establishes | What it does not |
| --- | --- | --- | --- |
| #190 | https://github.com/ZX7-Labs/Zx7-creative-studio-/pull/190 | Host-owned crash-durable request admission; no replay of the same native request ID | Native mutation applied |
| Installed BODY bridge | main commit `dce1cb5b548e05b3348517f6fe86a21f7458d4f8` | Opt-in durable write admission on real registered BODY adapter | All clients enabled by default |
| #192 | https://github.com/ZX7-Labs/Zx7-creative-studio-/pull/192 | Shared version-aware SQLite FULL-sync policy; fast universal core gate | Whole renderer fidelity |
| #194/#195 | https://github.com/ZX7-Labs/Zx7-creative-studio-/pull/194 | Lease-owner fencing and real process-death tests for native artifact publication | User artistic sign-off |
| #196 | https://github.com/ZX7-Labs/Zx7-creative-studio-/pull/196 | Immutable source-validated original plan heads and exact expected-parent CAS | Native editor undo/redo validated |
| #197 | https://github.com/ZX7-Labs/Zx7-creative-studio-/pull/197 | Atomic CAS across up to 32 independently validated instrument plan heads, including killed-process rollback | Atomic cross-application file edits |
| #198 | https://github.com/ZX7-Labs/Zx7-creative-studio-/pull/198 | Durable recovery inventory across restarts for unverified native tool writes | Independent native-state reconciliation |

Architectural single sources: `AGENTS.md`, `ENGINEERING_STANDARD.md`, `CAPABILITIES.md`, `studio_next/capability_gateway.py`, `studio_next/capability_attempts.py`, `studio_next/body_project_heads.py`, `studio_next/body_publication.py`. Do not add a parallel generic ledger if an existing host-owned one can be extended safely.

## Real local-model experiment — observed failure, not guessed cause

**Workflow:** https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/42149908182  
**Exact trial source:** `8a7ea4958a4450e4a997ee6d26d18a10e3bc8037`, on draft research branch `engineering/unified-brain-body-architecture-audit-20261106`. This is NOT merged into `main`.  
**Upstream native editor:** pinned Velorn submodule `b3c02adbd5c0779feb8abf34978299e9502cc0e7`, reused as an actual installed editor rather than rewritten.
**Evidence:** workflow artifact ID `13471688477`, uploaded `evidence.json`, `native-journal.jsonl`, `journal-audit.json`. The artifact was created with **five-day retention**, so the following privacy-bounded facts are deliberately committed here. The camera media and original model prompts **are not committed**.

Independently observed facts:
- A real camera source (240.032 s, 44,353,030 bytes, fixed SHA `52d9b05bec542094c5bada760bad18af2fdbec03374488db65ae0f45ef96184f`) passed complete source video decode. Wikimedia metadata claimed CC0; **legal rights were not independently certified**.
- Pinned local Qwen3.5-2B Q4_K_M model and vision projector checksums matched the lock. The child model process peak VmHWM was 3,351,195,648 bytes; this is **not** total application/system RAM.
- The actual model selected native `create_project`; native application ACK and host READs subsequently established an opened project.
- The model previewed `import_asset_from_path`, then applied an import. After a lag, host READs observed **one** real native asset in `get_assets`. An initial zero count was **not** final evidence of a missing import.
- The model then selected `add_assets_to_timeline`. The native host returned a reported error; the harness correctly **stopped without automated replay**. Actual tool arguments and private native error text are available in the short-lived evidence only as hashes, **not** enough to assert the cause.
- `model_status=native_error_requires_state_reconciliation`; **0** image inputs sent to the model, **0** model mutations after visual observation, **0** verified exports, **0** saved native projects; `technical_trial_completed=false`, `artistic_quality_approved=false`. Journal chain structure passed its audit; that is not physical edit quality.
- The independent no-model physical native editor E2E **passed earlier** at https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/42125875987, including actual project/asset-ID read convergence. It cannot be presented as evidence that Qwen edited the film.

**Interpretation:** This trial narrowed the blocker to the *model ↔ native timeline-placement boundary after real import*. A precise parameter/schema/asset-ID cause is **not verified**. Do not claim an engine bug, a model bug, or an artistic limitation on this evidence alone.

**Cheapest next experiment:** Under exact current pinned native source, instrument the host's pre-dispatch *schema and live-ID validation* and retain only bounded categorical rejection reasons (e.g. missing field, wrong type, native-ID-not-observed, precondition not met). Compare the model-selected timeline arguments against the installed tool's declared ABI **without recording unredacted private source paths or creative prompts**. Confirm whether failure was rejected *before* dispatch or occurred *after* native invocation. On any uncertain write, conduct READ-only state reconciliation; do not replay automatically.

**Pass condition:** A genuinely local model, without scripted edit choices, selects a native source, places it on the actual timeline, observes source-bound decoded frames, chooses an independent revision, saves/reopens the editable project, and yields an independently decoded export with real original-source custody. **Kill/redirect condition:** If repeated controlled evidence with confirmed valid tool contracts/IDs still shows no creative revision, benchmark a different pinned open-weight model instead of adding prompts that secretly encode editor mutations.

## Ranked cross-domain gaps / pre-mortem

1. **Independent native-state commit witnesses — OPEN.** Durable admission, immutable plan heads and media publication are implemented, but they are distinct claims. Build one host-owned operation lifecycle with pre-state revision, physical READ-only post-state witness, uncertain-write suspension, explicit owner reconciliation and durable receipt; engine-specific observers plug in. Do not equate MCP transport success with native application commit.
2. **Model navigation and recoverable error feedback — OPEN.** Avoid spending dozens of inference turns rediscovering a prerequisite after host already knows it. Keep host-discovered tool names, exact source IDs and field schemas truthful. A pre-dispatch validation error may be corrected; an ambiguous post-dispatch error needs independent observation. Never hide this distinction.
3. **One project across engines — PARTIALLY PROVEN.** Atomic immutable *plan selection* exists; a cross-application transactional edit/save/export protocol has **not** been demonstrated. Preserve editable source and isolate partial failure.
4. **Security and OSS/license provenance — OPEN for new engine surfaces.** Use installed host grants, sandbox untrusted execution, source content rights, GPL engine source/notice obligations, owner workspace isolation, no private media in CI artifacts. Do not infer that a local runtime is automatically secure.
5. **Capability acceptance / release gate — OPEN.** Measure source-custody, frame/audio fidelity, exact saved native state and human-reviewable artistic results per engine. Full green CI is not a general creative-quality badge.

## Repeatable continuation protocol — to survive chat limits

1. Read `AGENTS.md`, `ENGINEERING_STANDARD.md`, `CAPABILITIES.md` and this document; inspect **live** `main` HEAD, outstanding PR stacks, and exact-head CI results through GitHub.
2. Pick the largest cross-capability unknown, not a random video-only defect. Name success and kill conditions before spending on a full end-to-end model trial. Isolate narrow tests first, then physical/editor/model checks.
3. Commit code, regression tests and concise *non-sensitive* observations onto a named GitHub branch. Create a small PR against `main`; never throw an unfinished 300-commit stack into the default branch.
4. Do not merge new source until exact-head relevant gates pass and the diff is reviewed. If unfinished, leave branch/PR and blocking evidence in GitHub; do **not** imply it is on `main`.
5. Keep private camera/video, user rights records, unrestricted prompts, access tokens and local absolute paths **out of public GitHub**. Record input digests and redacted diagnostic classifications only.
6. At each milestone, update this handoff's last-verified facts and source links. Each next conversation can continue from GitHub without relying on assistant chat memory.

**Design decisions:** Reuse the installed Velorn engine and existing SQLite BODY ledgers, preserve all authored originals, keep experimental model work quarantined in draft PRs, require physical evidence before claims, and make new engine types extensions of one BODY authority—not separate products. These are reversible engineering choices, not user permission to spend money or change security/legal policy without approval.
