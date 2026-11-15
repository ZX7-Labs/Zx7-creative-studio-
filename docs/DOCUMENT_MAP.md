# ZX7 documentation and source-of-truth map

> This is a navigation and authority index, NOT another status ledger. Reorganized by *meaning* rather than moving older files: Git history, source links, external PR discussion and native source pins remain intact. A file's date or name does not make historical statements current.

## The two lanes (read in this order)

**LOCKED / NORMS / BUILD:** [BUILD_BLUEPRINT](BUILD_BLUEPRINT.md) is the single implementation-facing fixed build plan. Underlying owner authority remains [CAPABILITIES](../CAPABILITIES.md), [ENGINEERING_STANDARD](../ENGINEERING_STANDARD.md), [AGENTS](../AGENTS.md), [BRIEF](../project-brain/BRIEF.md) and [Master Plan](ZX7_CREATIVE_STUDIO_MASTER_PLAN.md). Only an explicit owner delta or carefully recorded evidence-backed supersession changes normative scope. Creative fabric as outcome is locked; the CSF implementation hypothesis is not.

**CHANGING / EVIDENCE:** [current STATE](../project-brain/STATE.md) + [typed execution ledger](../project-brain/EXECUTION_LEDGER.json) identify active priority, scope of proven foundations, the failed trials and the next acceptance gate. [RISKS](../project-brain/RISKS.md), [failure forensic register](../project-brain/EVIDENCE/FAILURE_REGISTER.md), [EVIDENCE INDEX](../project-brain/EVIDENCE/INDEX.md) and real Git/Actions runs hold causal and historical proof; [DECISIONS](../project-brain/DECISIONS.md) is append-only rationale. Refresh current main/PRs/CI before acting on a snapshot.

**Never maintain a third 'latest status' document.** `STATE.md` is the sole human current pointer. JSON is the structured status index of the *same* reality, not a conflicting source of truth. If either is stale, inspect actual Git/source, reconcile both in the same reviewable change, retain contradictions as pending until resolved. Raw events remain original tool logs/artifacts or access-controlled archives, not rephrased in JSON as if exact transcripts.

## Authoritative / enduring product and engineering source

| File | Responsible information | Change rule |
|---|---|---|
| [CAPABILITIES.md](../CAPABILITIES.md) | Original complete A–L professional scope, hard acceptance and owner creative freedoms | Founder requirement delta only |
| [ENGINEERING_STANDARD.md](../ENGINEERING_STANDARD.md) | Quality, delegated engineering method, one active field and owner showcase | Normative engineering decision |
| [AGENTS.md](../AGENTS.md) | Agent entry and constraints | Keep aligned with latest BRIEF and documentation navigation |
| [project-brain/BRIEF.md](../project-brain/BRIEF.md) | Founder objectives, latest paid/private model-use boundary | Owner delta; preserve superseded original in Git/DECISIONS |
| [docs/ZX7_CREATIVE_STUDIO_MASTER_PLAN.md](ZX7_CREATIVE_STUDIO_MASTER_PLAN.md) | Chronological reasoning, 6-part fabric goals, G0–G4, full T01–T24 and research atlas | Design rationale; preserve historical baseline and hypothesis labels |
| [docs/BUILD_BLUEPRINT.md](BUILD_BLUEPRINT.md) | **Consolidated implementation-ready fixed scope** and source ownership, safe architecture, A–L exit and G1 creative loop | Edit only when product contract or accepted architecture changes |
| [docs/continuity/WORKING_AGREEMENT.md](continuity/WORKING_AGREEMENT.md) | Engineering collaboration discipline | Normative, stable |
| [docs/zx7-universal-execution-architecture.md](zx7-universal-execution-architecture.md) | Source-neutral execution ADR and host budgets | Historical design decision; supersede explicitly |

## Engineering architecture, usage and research (NOT current acceptance)

| File | Purpose | Caution |
|---|---|---|
| [README.md](../README.md) | Build, install and public owner/developer usage | A command passing does not mean field certification |
| [docs/architecture.md](architecture.md) | Native authority, data planes, project state and technical tradeoffs | Review against current source before coding |
| [docs/reuse-research.md](reuse-research.md) | Engine selection, source research and comparative measurements | Research is scoped to the original tests/dates |
| [docs/video-research-plan.md](video-research-plan.md) | Early R1–R4 / P1–P5 work rationale | Not the live task board |
| [docs/nvidia-byok.md](nvidia-byok.md) | Optional hosted provider setup and consent | Latest BRIEF forbids default paid runs |
| [engines/velorn/README.md](../engines/velorn/README.md) | Exact pinned installed native editor, integration, opt-in source variants | Source/version-specific contract, not full product status |
| [research/browser-engine/README.md](../research/browser-engine/README.md) | Bounded browser-motion research probe | No mandatory runtime browser-engine proof |

## Changing engineering state / historical evidence

| File | Purpose | Update rule |
|---|---|---|
| [project-brain/README.md](../project-brain/README.md) | Entry/navigation protocol | Keep small, no second progress diary |
| [project-brain/STATE.md](../project-brain/STATE.md) | **Only current compact human checkpoint** and single next blocker | Replace stale snapshot; refresh GitHub; ≤14 KB |
| [project-brain/EXECUTION_LEDGER.json](../project-brain/EXECUTION_LEDGER.json) | Typed A–L, implementation, acceptance, failures, PR overlap and open gates | Refresh with exact source references; validate schema and no unsupported PASS |
| [project-brain/RISKS.md](../project-brain/RISKS.md) | Active failure risks with exit criteria | Link evidence; do not close by assertion |
| [project-brain/DECISIONS.md](../project-brain/DECISIONS.md) | D001+ append-only reason and supersession | Append only on substantive decisions, never rewrite history |
| [project-brain/PROJECT_MAP.md](../project-brain/PROJECT_MAP.md) | Native/source responsibility map | Refresh stale implemented-vs-draft status |
| [project-brain/EVIDENCE/INDEX.md](../project-brain/EVIDENCE/INDEX.md) | Positive and negative exact source/PR/workflow index | Append relevant evidence, retain historical negative |
| [project-brain/EVIDENCE/FAILURE_REGISTER.md](../project-brain/EVIDENCE/FAILURE_REGISTER.md) | Verified failed model/physical experiments, actual root layer, fix status and retest state | Do not label a source fix as successful real-model retest |
| [project-brain/STATE-2026-11-15-ARCHIVE.md](../project-brain/STATE-2026-11-15-ARCHIVE.md) | Exact prior long STATE content when current snapshot was compacted | Frozen archive only |
| [project-brain/EVIDENCE/2026-11-10-INHERIT.md](../project-brain/EVIDENCE/2026-11-10-INHERIT.md) | First repository handoff audit and historical source limits | Frozen evidence |
| [project-brain/EVIDENCE/2026-11-10-NVIDIA-ONE-SHOT.md](../project-brain/EVIDENCE/2026-11-10-NVIDIA-ONE-SHOT.md) | Detailed verified NVIDIA real-model failure report | Frozen report + later fix references |
| [project-brain/EVIDENCE/2026-11-12-G0-COVERAGE.md](../project-brain/EVIDENCE/2026-11-12-G0-COVERAGE.md) | Original G0 A–L trace and proposed F01–F14 fixture definitions | Fixture *spec*, not PASS ledger |
| [project-brain/EVIDENCE/2026-11-13-AI-NATIVE-PERCEPTION-RESEARCH.md](../project-brain/EVIDENCE/2026-11-13-AI-NATIVE-PERCEPTION-RESEARCH.md) | Perception comparison H-PERCEPTION-01 and untested P0–P3 | Research hypothesis not current behavior |
| [docs/continuity/STATUS.md](continuity/STATUS.md) | Historic large continuity checkpoints | **Archive only**, never live source |
| [docs/continuity/RESUME_PROMPT.md](continuity/RESUME_PROMPT.md) | Optional minimal agent re-entry | No hardcoded stale active provider/run |

## Operational update and no-duplication protocol

- For a new behavior requirement: check fixed product authority → make an explicit design/owner decision only if needed → update blueprint. **Do not rederive a 90 KB master plan per chat.**
- For a completed code/test result: attach real source SHA, changed project/source revision, exact PR/run/job and physical outcome; update JSON ledger + STATE and relevant EVIDENCE/RISKS. A merged PR is *implementation*, not professional acceptance.
- For a failure: preserve original logs/artifact digest and source URL, exact observed symptom/stack, root cause confidence, proposed fix, whether fix merged, and whether a comparable *real neural* retest passed. Keep source-level regressions separate from model proficiency.
- For a status change: define what tier passed: `source_present`, `offline_tested`, `physical_native_tested`, `real_model_trial`, `independently_accepted`; never infer one from another. An acceptance gate is NOT complete while a required tier is missing.
- Before starting: query exact live main, open PR overlap, latest relevant positive AND negative records. Resume the smallest blocked end-to-end owner outcome; no speculative “make CI green” work.
- When saving exact model/tool traces: use machine-readable run events (`event_id`, model/settings, source SHA, time, session/turn, tool intent, result/ack, effect classification, native revision, export digest, error), but keep private payload and tokens out of public Git. A linked summary is not raw evidence and an expired artifact is not retrievable.

## External practice research used for the structure

- [Anthropic long-running agent harness](https://www.anthropic.com/research/effective-harnesses-for-long-running-agents): explicit progress and source-verified continuation, rather than context compaction alone.
- [Google Cloud ADRs](https://docs.cloud.google.com/architecture/architecture-decision-records): append decisions with rationale and supersession near code.
- [OpenAI agent tracing](https://openai.github.io/openai-agents-python/tracing/): structured actual model/tool action spans distinct from a prose recap.
- [Diátaxis](https://diataxis.fr/): keep reference, explanation, guides and evidence separate.
- [GitHub artifact retention](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository): no infinite evidence retention promise.

**Format decision:** English Markdown for the fixed human/agent engineering contract, JSON for validated changing project-state indexes, original Git/Actions logs for raw provenance, and future JSONL only for events actually captured by the runtime. XML adds schema/verbosity without a current requirement. Hindi/Hinglish is fine for owner conversation; identifiers, code and contracts remain English.
