# ZX7 Creative Studio — Fixed Build Blueprint (implementation contract)

> **Purpose:** one implementation-facing **derivative of the original owner requirements**, not a new product version, upgrade proposal, competing authority, status file or claim of implementation. If it appears to differ from CAPABILITIES, current BRIEF or the original Master Plan, stop and reconcile their exact wording; do not automatically prefer the newest file.
>
> **Authority:** [CAPABILITIES.md](../CAPABILITIES.md) is the full A–L scope; [ENGINEERING_STANDARD.md](../ENGINEERING_STANDARD.md) and [AGENTS.md](../AGENTS.md) govern engineering; [founder BRIEF](../project-brain/BRIEF.md) controls explicit owner changes; [Master Plan](ZX7_CREATIVE_STUDIO_MASTER_PLAN.md) retains original reasoning, examples, and G0–G4/F01–F14/T01–T24. This blueprint consolidates implementation instructions without deleting or silently superseding any of them. If a future owner delta conflicts, record it explicitly in [DECISIONS](../project-brain/DECISIONS.md).
>
> **Fixed goal ≠ fixed technique.** Building an AI-native creative control/perception **fabric** is an intended product outcome. The *particular* Creative State Fabric (CSF) representation, API, engine, optimizer, and whether a medium beats existing native tools are G2 falsifiable design hypotheses—not authorized as proven universal formats. Do not confuse “we will build a powerful creative fabric” with “we must ship this first proposed CSF class hierarchy.” Scope must not shrink if the hypothesis fails.
>
> **Strict separation:** this file states *what must exist and how to judge it*. Current implementation, failed model runs, unfinished PRs, provider permissions and evidence status belong to [STATE](../project-brain/STATE.md), [EXECUTION_LEDGER](../project-brain/EXECUTION_LEDGER.json), [RISKS](../project-brain/RISKS.md) and [EVIDENCE](../project-brain/EVIDENCE/INDEX.md). Do not copy dated result claims back into this fixed file.

## 1. Product to build — locked owner outcomes

Build **one professionally usable, original, open-source, local-first, self-hostable, model-independent ZX7 Creative Studio / BODY**. A replaceable, genuinely capable creative Brain can research appropriate material, originate ideas, choose **both the art and its method**, inspect actual authorized workspace/media, compose across specialist engines, test the effects of its work, critique genuine image/motion/audio, surgically revise, preserve human work and native editability, and deliver independently verifiable results. It must not require one proprietary model, paid API, hardware vendor or hosted inference service at runtime.

This is a complete, future-extensible creative production environment, not a toy film generator, an editor clone, a 130-tool facade, a hard-coded recipe, or a promise that every artistic task can be executed by today's weakest model. Full A–L scope remains binding. Video/NLE C is one integration workload with A/B/F/G/I/J dependencies, not a mandatory prerequisite for independent studio domains.

Founder priority ordering **(preserve): originality → production-grade system strength → disciplined design/UX → independently measured business value**, except where lower-priority concerns imply serious safety, privacy, rights or reliability harm. “Best” is a comparative, falsifiable aspiration across art, correct media, expressiveness, latency, memory/VRAM, cost, stability, maintainability, portability and accessibility, not a marketing label earned from CI.

The Brain may be general, specialist, local or separately authorized hosted; capability ceiling is in BODY and model competence is judged separately. Do not make the runtime Brain an engineering assistant with eight simulated personalities. Engineering work may apply eight *lenses* (architecture, science, research, software, systems, design, evaluation, security) without pretending to have eight independent reviewers.

## 2. What is fixed vs how we build it

| Status | Product/engineering decision | Evidence/authority |
|---|---|---|
| **FIXED** | One coherent source-aware shared workspace; authoritative domain-native project owners; safe cross-engine links | Canonical A–L, Master Plan §§2–4 |
| **FIXED** | Brain chooses artistic intent and appropriate means; host owns permissions, source truth, physical verification | Master Plan §§4–5 |
| **FIXED** | Visually AND audibly meaningful temporal sensing; not merely numeric stats or file existence | A–L J/G, Master Plan §5.5 |
| **FIXED** | Real saved editable project, original asset custody, non-destructive revisions, truthful undo/reopen, human override | A/B/C/I/K |
| **FIXED** | FOSS, local-first, no required paid-model dependency; independent security and rights acceptance | BRIEF, CAPABILITIES |
| **FIXED** | Complete all A–L; professional evidence before claiming each field; G1 before claiming C | Master Plan §11, ENGINEERING_STANDARD |
| **PREFERRED REUSE RULE** | Inspect existing source-owning native engines, graphics, host gateway, journal and project heads before new systems; actual installed capability and pins belong to the live source map | ENGINEERING_STANDARD and PROJECT_MAP |
| **CANDIDATE / G2** | CSF minimal typed fabric coordinating intent/observations/actions, adaptive router, model-optimized procedural medium | Master Plan §5, G2; NOT an already proven API |
| **CANDIDATE** | Runtime specialist models, agent-memory indexes, rich learned perception, safe procedural grammar, exact interchange adapters | Measure expressive gain, cost and safety before adoption |
| **REJECTED APPROACHES** | Mandatory GUI imitation, tool-only/code-only dogma, fake universal film JSON, fictional always-on agents, or treating scripted CI as creativity | Master Plan §10 and DECISIONS |
| **VARIABLE PERMISSIONS** | Always consult the current owner BRIEF and live host grants for paid/private inference; this fixed build contract is NOT an authorization snapshot | BRIEF and trusted host |

“Implement the fabric now and upgrade later” means **finish a genuinely useful baseline fabric connecting native truth, creative control and observations first**. Defer embellishments and unproven abstractions; do not defer mandatory safety, artistic capabilities, or source preservation. Any claimed later upgrade must be optional/additive and benchmarked.

## 3. Minimal integrated system — owners of truth

```text
Owner creative brief + rights-granted source
             │
     Replaceable creative Brain
       (intent, route, critique)
             │
  ZX7 trusted creative execution boundary
  ├─ current live capability discovery, contracts, permission grants
  ├─ resource/cost budgets, source IDs, transaction/attempt journal
  ├─ native revision preconditions; safe constrained procedure when needed
  ├─ source-identified observations and verifiable outcomes
  └─ workspace revision/human-intervention reconciliation
             │
 Native source-owning engines (Velorn / MLT / FFmpeg / Blender / graphs / specialists)
             │
 Actual editable native documents + original media custody
             │
 Physical render/decode → timed visual/audio evidence → review/targeted revision
             └─────────────────────────────────────────── back to Brain
```

**Maintain existing code and authorities**, inspect current interfaces before adding modules:

- `studio_next/capability_fabric.py`, `capability_gateway.py`: live catalog and host-granted typed admission; the Brain cannot invent permission from descriptions.
- `studio_next/native_creative_control.py`, `native_editor_session.py`, `body_editor_mcp.py`: bounded native model/editor control; distinguish non-dispatch, confirmed no-write and *uncertain* write.
- `studio_next/media_vault.py`, `body_archive.py`, `body_publication.py`: physical source custody, rights/grants, records and safe publication.
- `studio_next/durable_graph.py`, `durable_sqlite.py`, `capability_attempts.py`: already present durable jobs and attempts; no second orchestrator/DB.
- `studio_next/body_project_heads.py`, `body_project_revision.py`: versioned project/document heads; native editor remains authoritative about actual timeline and GUI undo.
- `third_party/velorn`, `engines/velorn/`, `studio_next/body_mlt_*`, `precision_retime.py`, `composite_mix.py`: actual NLE, picture/sound/clock and source-bounded edits.
- `studio_next/body_visual_graph.py`, `body_visual_render.py`, `blender_scene.py`, `body_motion_project.py`, `body_exr_passes.py`: native creative authoring without flattening original sources.
- `studio_next/body_observation.py`, `body_review_compare.py`, `body_creative_session.py`: real observed media/notes and revision evaluation; semantic skills still must be proved.
- `studio_next/body_service.py`, `body_mobile.py`, `body_desktop.py`: owner-facing entry points to inspect, not presumed secure remote production systems.

**One project envelope, multiple real documents:** link stable project UID, native document and revision, object IDs, original SHA/rights, rational video/audio time, coordinate/color/alpha meaning, relationships and loss constraints. Domain originals (`.blend`, editor native project, graphics graph, audio stems, EXR) keep ownership. No generic fake film shots in an audio-only or 3D-only project; no lossy conversion silently called “editable”.

## 4. The creative fabric: six responsibilities and executable interfaces

The fabric is an **outcome contract** using existing gateways and native sources first. Do not create six microservices for six concepts.

**Runtime attachment:** a compatible replaceable Brain receives actual capabilities through executable discovery and typed native contracts, observes current state, acts within host grants, receives verified results and adapts. No runtime Markdown or manually authored creative prompt pack should be required. The user's brief is intent, not an engineered action script. Protocol metadata and provider transport instructions are distinct from creative scripts; verify which existing instructions remain necessary and remove redundant dependencies only with regression evidence. Measure latency, competence and cross-domain operation rather than claiming an API key creates automatic expertise.

1. **Intent** — arbitrary creative goal, user constraints, context, alternatives and intent provenance. The host must not hardcode genre, mood, camera, duration, style, cut count or a cheaper default artwork.
2. **State** — real versioned native clips/tracks, masks/keyframes, vector/text shapes, objects/meshes/lights/camera, mixer channels and sources. Observe current real object identities, exact rational clocks, coordinate spaces, original rights and grant boundaries.
3. **Perception** — source-bound actual decoded frames at relevant intervals, moving sequence where needed, genuine audible signal and semantic observations only with a compatible model. Return time coverage, uncertainty and source; numeric loudness/transcripts alone cannot certify listening, acting or emotion.
4. **Expression/Action** — the Brain chooses legitimate native tool, editable graph, safe isolated procedural code/shaders, separately licensed generative specialist, GUI fallback or their combination. Contracts specify inputs, target revision, authority, resources, expected editability, fallbacks and unsupported effects.
5. **Verification** — post-write native readback, actual decoded picture/audio, media profile and custody checks, reversible revision comparison, calibrated creative assessment and separate independent reviewer evidence; do not conflate these layers.
6. **Experience/Memory** — long-lived approved intent, selected alternatives, observed failures and their exact source refs, latest human edits, executable next step and durable checkpoints, with stale-state and untrusted-content protection.

**Minimum proposed internal operations, NOT promises that matching APIs already exist:** `observe_project(project_uid, expected_revision, required_scope)`, `discover_capabilities(intent, grants)`, `propose_action(intent, source_id, native_object_id, expected_revision, means, parameters)`, `validate_and_dispatch(action, bounded_budget)`, `observe_physical_result(native_revision, artifact_digest, intervals)`, `compare_and_revise(base_revision, current_revision, intent)`. The implementation maps onto existing exact tool schemas; never silently manufacture parallel RPCs just to fit these names.

Security invariants: reject stale native revision and fabricated IDs before writes; reject ambiguous side effects without auto-replay; keep source bytes immutable; preserve unknown native metadata or fail closed; isolate generated programs with no default network and bounded CPU/GPU/RAM/time; refuse raw private sound/image cloud transport without separate explicit consent. Human changes invalidate stale Brain snapshots. A refusal is better than silently changing the requested creative direction.

## 5. G1 audiovisual workload: observable real creative loop

This is an integrated audiovisual acceptance workload, not the sole next task or a prerequisite for independent A–L integration. Use a complete legally safe audiovisual assignment to advance capability depth until its acceptance gates pass. Use deliberate varied follow-up briefs, not one scripted style.

**G1-01 — Admission and genuine creative choices.** Given natural-language brief, rights-cleared source, expected visual/audio targets and host grants, a *real model* chooses a nontrivial original creative plan and practical route based on actual installed affordances. Model/tool provenance is captured. Host may reject impossible/unsafe actions but cannot write the aesthetic decisions. Check that no engineer-authored timeline/cut list impersonates model choice.

**G1-02 — Native source-backed creation.** Materialize original picture and sound using existing BODY+Velorn/MLT/graphs/Blender as appropriate. Keep untouched originals and exact SHA, editable document version, source window/clip ID, rational frame clock and sample clock. Confirm saved native project can reopen in a fresh app.

**G1-03 — First conforming delivery.** The *actual chosen export options*, independently read from the pinned app, satisfy the brief (picture, duration, codec, aspect, audio/stems). Decode the complete physical result; do not trust requested resolution, filenames, a success string or a render-start receipt. Keep bounded artifact reference and digest.

**G1-04 — Genuine temporally grounded observation.** The model selects task-relevant frame windows and meaningful audio intervals; sees actual visual sequence and, with a capable modality and permitted transport, hears/understands actual timed sound. Annotate what was observed vs inferred vs unobserved. Compare against explicit creative intent. Real visual and audio semantics are mandatory to claim general creative review.

**G1-05 — Independent targeted revision.** Brain chooses a precise justified native change, guards actual object and revision, retains first output, saves a distinct editable second revision and fully decodes a distinct conforming second output. Verify targeted change and no unrequested loss. The model must be able to reject poor edits or stop with a truthful gap.

**G1-06 — Human joins without losing work.** Actual user can inspect/manually change the *same current native workspace*, pause/review/override and resume AI. Stale proposal rejected or reconciled without overwrite; undo/reopen preserve user change. X11 synthetic pointer moves are engineering evidence, not a replacement for a human usability study.

**G1-07 — Failure, security and quality.** Attempt invalid source ID, stale head, license/revocation, malformed model tool call, uncertain write/crash, refused private-media egress and wrong output profile. Record exact layer and cause. Independently grade varied original results against a competent existing professional baseline, including visual timing, intelligibility/mix and aesthetic defects. Graders can disagree; record disagreement, not an invented universal quality percentage.

**G1 exit condition:** all relevant source/rights, actually applied native state, physical picture+sound, autonomous selection, semantic review, nontrivial revision, human collaboration, recovery and independent artistic/security gates accepted on an exact version. Never declare field C complete from an internal fixture, test count, 320×180 clip, or a hosted model reputation. Only after defensible field completion show the owner a concrete original film as a completion showcase. Other independent domains can progress before this gate closes.

**Historical experiments are not fixed requirements.** For real model failures, subsequent source fixes, comparable retests and current permission, read the [mutable failure evidence](../project-brain/EVIDENCE/FAILURE_REGISTER.md) and [execution ledger](../project-brain/EXECUTION_LEDGER.json).

## 6. Full A–L: owner outcome, source foundation, distinct closure evidence

A **Truth, custody, rights.** Build lawful source intake, owner/licensing assertions with independent check where relevant, immutable originals, permissioned reuse, revocation, artifact lineage, recoverable relocation, separate private/public publication. Start `media_vault.py`, archive/publication. Exit: actual revoked/forged/untrusted content cannot sneak into authorized export; backup/restore and rights identity verified.

B **Coherent editable project.** Preserve native source semantics across video, sound, graphics, 3D, color; support non-destructive graph/clip revisions, portable references, safe loss-aware exchange and fresh app reopen. Start project heads, Film IR (film-only), OTIO, Velorn/MLT. Exit: two-way roundtrip/transfer with no silent effects, clocks, channels or unknown-field loss; if impossible, reject explicitly.

C **Professional nonlinear video.** Real multitrack cuts, trims, ripple/roll/slip/slide, speed, effects, transitions, keyframes, original media, subtitle timing, picture/audio sync, real undo, working interface and expressive model control. Start Velorn/MLT/precision_retime. Exit: arbitrary *model-authored* editor results and comprehensive professional creative/technical tests including failure recovery and cross-media fidelity.

D **Graphics, photo, vector, typography, 2D/2.5D motion.** Original editable paths/geometry, fonts/kerning/legal font assets, masked/tracked/rotoscoped image, alpha, curves, motion/composition and hand-precision work. Start visual graph/planar/motion studio. Exit: professional varied editable designs with raster/alpha/time comparisons, font/license and reopening evidence.

E **CGI, 3D, VFX, simulation.** Native meshes/rig/skin, nodes/materials/lights/cameras, constraints, particles/physics, motion, compositing, EXR passes and multi-view temporal review. Start `blender_scene.py`, CGI and motion modules. Exit: independent original nontrivial scenes editable in Blender or relevant native engine after revision/restart with measured quality, safe code boundaries and rights.

F **Color and delivery mastering.** Correct declared primaries, transfers, alpha, scene-linear/OCIO/ACES2, >8-bit SDR/HDR, gamut mapping, reproducible viewing/render and final masters. Start `body_aces2_movie.py`, color/film finishing. Exit: calibrated physical transforms and cross-engine delivery fidelity, not just LUT code or BT.709 sample.

G **Sound, music, voice and subtitles.** Real dialogue/music/SFX, licensed voice/source integrity, multitrack/stems and channel mapping (including 5.1 where requested), sound edit, fades/gain/EQ/dynamics, true peak/LUFS, sample-clock sync, language/subtitle fidelity and actual listening. Start `composite_mix.py`, `body_loudness.py`, voice lab. Exit: timed semantic hearing and independent listening/mix judgment, not numeric sound tests.

H **Licensed original media generation.** Replaceable installed models/weights/audio/video/3D with documented license, compute, consistency, prompt/seed, physical output and source/controllability limits. Start Comfy/provider adapters. Exit: actual authorized generation, distinct long-range temporal quality, proper rights and reversibility disclosures, not an API adapter alone.

I **Reliable multi-engine execution.** Live semantic capability discovery, exact typed host grants, budgets, durable attempt/lease, failure isolation, concurrency, replay safety, cancellation, transactions across separately owned native state and bounded throughput. Start capability gateway, attempts, durable graph. Exit: crash/power/network/stale-host fault matrices, truthful uncertain state and measured latency/CPU/GPU/cost.

J **Perception and intentional self-correction.** Source-linked temporal vision, audible semantics, story/acting/visual defects, original/edit comparisons and task-calibrated critiques without false confidence. Start observation/review/session. Exit: actual model chooses appropriate senses and corrects failure on held-out briefs; human/professional blind comparison judges improvements.

K **Owner interface, live collaboration, mobile/privacy.** One usable interface for create/inspect/preview/edit/compare/stop/revise/undo/recover/export; accessibility, safe local-first install, backups, protected HTTPS remote/Android when released, privacy and credential isolation. Start Velorn + owner desktop/client/mobile/service. Exit: fresh supported owner performs meaningful tasks; native human edits survive resumption; remote threat and usability tests.

L **Independent release-quality proof.** Cohesive source, packaging/notices, rights, model licenses, security, reliability, usability, measurable performance/cost, creative craft and diverse professionally assessed deliverables. Exit: independent technical and artistic reviewers against relevant baselines; no self-scored “world best”.

No entire A–L field is currently certified merely because its candidate modules exist. **F01–F14** in [G0 coverage](../project-brain/EVIDENCE/2026-11-12-G0-COVERAGE.md) are proposed representative fixtures; **T01–T24** in the [Master Plan](ZX7_CREATIVE_STUDIO_MASTER_PLAN.md) are verification scenarios. Mark individual outcomes only after independently attached real evidence.

## 7. The staged execution route and no-premature-upgrade rule

**G0 — Reconcile first, only once per relevant baseline.** Use [file ownership map](DOCUMENT_MAP.md), [live execution ledger](../project-brain/EXECUTION_LEDGER.json), main SHA, installed engines/availability, open PR overlap and negative runs. Existing full product planning is settled; do not generate another spec every session. Correct one source-grounded gap; avoid wholesale older-PR merges. G0 is complete only when current authority/ownership, all source links and next actual blocker can be resolved without founder rebrief.

**G1 — Finish authentic professional native creative video.** Follow §5; prefer reaching the missing model/artistic result over recycling previously passed native script fixtures. Complete source code, real semantics, independent grade and honest handoff together.

**G2 — Prove or reject the fabric representation and routing advantage.** On comparable video, motion, 3D and audio tasks, test **A** existing native tool baseline, **B** safe procedural/editable code route, **C** minimal adaptive creative fabric. Match model/settings, rights-cleared media, resource budgets, held-out briefs; measure task expressivity, actual quality, native fidelity, correctness, latency, cost, failure rate and security. *Kill C* if it adds cost/complexity without meaningful advantage; retain the fixed creative outcome using A/B. Do not begin with a giant unmeasured universal JSON.

**G3 — Complete integrated A–L.** Finish D/E/F/G/H and shared A/B/I/J/K with native interoperable creative projects rather than disconnected toys. Use real domain creative tasks; adaptive order follows dependencies, not arbitrary marketing phases.

**G4 — Ship safely after external acceptance.** Reproducible install, exact third-party licenses and notices, optional weight/media rights, owner UX, privacy/remote/mobile hardening, durable recovery, performance/cost, field-by-field independent technical/artistic confirmation and owner authorization for public launch.

**Stop/upgrade boundary:** first finish the minimal baseline whose creative decisions, perception and editing are real. New memory agents, optimization, semantic indexes, new representations, multi-model orchestration, premium GPU integrations and cloud accelerators are later *candidates*, not excuses to postpone missing foundations. If a mandatory product capability cannot be expressed by the baseline, extend via a measured safe escape hatch instead of a rigid “upgrade someday.”

## 8. Required engineering method for every implementation task

1. Read this locked product contract **and** current ledger/STATE, then refresh live main and relevant exact open PRs. Skip experiments already definitively tested; do not merge/reverify old code for its own sake.
2. Select the **highest-value unclosed user outcome** and the actual source owner, not the easiest workflow to make green. State hypothesis, baseline, acceptance, failure/kill conditions and privacy/license constraints before changing code.
3. Compare current exact source paths and installed native APIs, current third-party pins, actual failures/stack/artifacts. Correct the owning layer; reuse prior implementations. Avoid second scheduler, database, media store, agent swarm or generic framework.
4. Make the smallest *cohesive product-level* change. Keep exact source SHA/project authority, original data and existing user-facing behavior. Test-first for changed behavior; adversarial source/object/time/rights/permission paths.
5. Run focused offline and real native physical checks, then once a stable code head exists run necessary combined regressions. Do not claim external reviewer independence from self-review. Do not run paid inference merely to test source schema errors.
6. Real semantic/model or craft claims require separately authorized *actual* inference and held-out professional evaluation, with objective artifacts and failure history. Offline CI is a different tier of evidence.
7. Update **only mutable** [execution ledger](../project-brain/EXECUTION_LEDGER.json), [STATE](../project-brain/STATE.md), [RISKS](../project-brain/RISKS.md), [EVIDENCE](../project-brain/EVIDENCE/INDEX.md) and append a new decision **only if a decision actually changes**. Keep errors and tentative diagnoses distinct. Leave next executable task with exact preconditions.

For any accepted claim, record: source commit+pin, model/settings (if any), original rights/media hash, grants, native project/revision/source IDs, chosen tool decision, full event/acknowledgement refs, physical export hashes/stream facts, timed observation coverage, comparison verdict, independent assessor, cost/performance and artifact retention. **Raw traces belong in access-controlled evidence storage, not secrets/private media in public Git.** Markdown may link a trace but never impersonate its full event list.

## 9. Definition of done, anti-goals and source genealogy

A change is done when its specified behavior works, is reversible where applicable, error-handled, rights-safe, physically verified at its owning system, documented and has reproducible evidence. A domain is done only when its independent artistic/professional gates are satisfied. A user product is done only when the whole A–L system is usable, secure and independently accepted. These are deliberately different statuses.

**Do not:** preauthor the AI's art; hardcode one style/scene/film target; fabricate full listening from RMS; treat a request-sized MP4 name as verified resolution; report source import as native-editability in another application; infer real-model success from unit tests; erase failed branches/artifacts; duplicate design docs every chat; invent a powerful “new language” instead of proving it; claim a human reviewer ran when none did.

**Original source lineage (never delete):** [CAPABILITIES](../CAPABILITIES.md), [ENGINEERING_STANDARD](../ENGINEERING_STANDARD.md), [AGENTS](../AGENTS.md), [founder BRIEF](../project-brain/BRIEF.md), [Master Plan](ZX7_CREATIVE_STUDIO_MASTER_PLAN.md), [architecture](architecture.md), [universal execution architecture](zx7-universal-execution-architecture.md), [reuse research](reuse-research.md), [video research plan](video-research-plan.md), and [G0 F01–F14](../project-brain/EVIDENCE/2026-11-12-G0-COVERAGE.md). Founder personal PDF remains private; only nonsensitive requirements are reflected here.

### Engineering research informing documentation/process, not claiming ZX7 measured results

- [Anthropic — Effective harnesses for long-running agents](https://www.anthropic.com/research/effective-harnesses-for-long-running-agents): bounded task state, Git history and truthful resumption; ZX7 reuses project-brain instead of inventing a second agent-memory runtime.
- [OpenAI — Agents tracing](https://openai.github.io/openai-agents-python/tracing/) and [agent evals](https://developers.openai.com/api/docs/guides/agent-evals): distinguish model/tool spans from outcome grading; not a requirement to install any SDK or emit private traces.
- [Google Cloud — Architecture Decision Records](https://docs.cloud.google.com/architecture/architecture-decision-records): record options, reason and explicit supersession in existing DECISIONS.
- [Diátaxis](https://diataxis.fr/): keep instructions, reference, explanation and operational evidence separate to reduce contradictory documents.
- [GitHub Actions artifact retention](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository): run links and artifacts are not immutable forever; preserve nonsensitive provenance/digests and retain original outputs where legally/safely authorized.

**Language/format:** stable engineering contract in clear English Markdown with normative MUST/SHOULD only where intentional; precise source identifiers/code in English; respond to owner in their chosen Hindi/Hinglish. Changing status uses validated JSON and verifiable external event traces, not XML or copied chat summaries.
