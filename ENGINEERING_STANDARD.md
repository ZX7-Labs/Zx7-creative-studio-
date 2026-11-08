# ZX7 Engineering Standard — enduring operating mandate

> **The best currently demonstrated practice is a research baseline, not the ceiling of our ambition.** This document defines how an engineering AI or human contributor should *work*. It does **not** increase a model's inherent intelligence, make the deployed AI brain depend on a prompt, or certify that ZX7 BODY is exceptional today.

## Authority, scope and continuity

Read this alongside [AGENTS.md](AGENTS.md) and [CAPABILITIES.md](CAPABILITIES.md). **CAPABILITIES.md is the canonical product/scope/acceptance contract** (A–L); this file is the complementary execution standard. Existing licenses, security limits, exact source evidence and the owner's latest authorized instructions still apply. Do not use this file to invent requirements, erase earlier decisions or overrule safety.

The owner delegates ordinary technical discretion end to end: imagination, research, questioning, comparison, planning, design, algorithms, implementation, integration, tests, benchmarks, review and corrective decisions. Do not repeatedly hand routine decisions back to the owner. Use the owner's examples to learn the required *expressive freedom*, never as canned user stories, mandatory templates, fixed effects or ceilings.

The mission is one cohesive, capable, original, local-first, source-responsible **ZX7 BODY**. A replaceable AI brain should be able to inspect, reason over, control, hear/see, revise and deliver genuine editable projects through BODY. Preserve the distinction: BODY supplies controllable creative instruments, trustworthy state, bounded execution, sensing and recoverability; the brain chooses the art and actions. A written instruction is not a substitute for a real independent creative decision loop.

## The standard is multidimensional, not cosmetic

Aim at unusual excellence **simultaneously** in creative range, originality, intelligence of operation, professional fidelity, exactness, speed, efficiency, memory/VRAM/compute, latency, cost, source provenance, rights, security, safety, privacy, accessibility, portability, scalability, recoverability, observability, adaptability, interoperability and maintainability. Add measures specific to the operation, such as audio sample clocks, color spaces, native curve editability or render reproducibility.

- **No hidden sacrifice:** a stunning frame does not excuse broken audio, unsafe file access, destructive project conversion or missing recovery. A fast renderer does not excuse wrong frames. Test critical dimensions individually; do not bury a hard failure inside one aggregate score.
- **No prestige theater:** more dependencies, agent roles, model parameters, abstractions, files, features or novel algorithms are not intrinsically better. Prefer the simplest design that demonstrably satisfies all relevant constraints. Create a new method only when the evidence supports a real benefit.
- **No unsupported superlatives:** the goal can exceed present best practice; a claim that it does so requires dated, comparable, independently inspectable evidence across the claimed workloads and quality dimensions. State uncertainty and coverage.
- **No frozen constraints:** a user's concrete example, sample length, existing engine or test fixture does not constrain the general creative language. Limits should originate in justified security, correctness, physical resources or explicit user requirements.

## Own the whole reasoning-and-engineering cycle

**1. Recover reality, then question the problem.** Read the current repository tree, main, open PRs, exact commit CI and relevant primary code. Inspect existing tests, engines, licenses, upstream fixes, docs, artifacts and past research. Distinguish historical evidence from current behavior. Identify missing requirements, non-obvious failure modes, assumptions, counterexamples and dependencies independently. Do not restart research that is already sound; do not defend a past design only because effort went into it.

**2. Define a hard, testable field-completion contract.** Start with representative professional workloads, counterexamples, granular edit controls, actual resource profiles, expected native/interchange state and adverse conditions. Specify correctness and rights/security gates, source/clock/color/audio/visual or 3D-specific oracles, genuinely editable exports, restart and human usability. Plan differential tests against trusted references. A list of tools or a successful short render is not completion.

**3. Research beyond fashionable solutions.** Examine strong current and historically useful open-source applications, libraries and architectures, upstream source, patches, license obligations, actual tool surfaces, research papers and reproducible independent evaluations. Study commercial professional workflows as references, not presumed permitted runtime dependencies. Compare equivalent workloads; date and version findings; include rejected alternatives, assumptions, maintenance burdens and falsifiable performance hypotheses. Combine ideas across disciplines when justified.

**4. Choose a defensible architecture, not an ideology.** Adopt and integrate a capable complete open-source application when it already solves a problem well; fork/adapt to close verified gaps; compose complementary engines only where boundary losses are understood; build from scratch when evidence shows reuse cannot meet essential controls or would cause worse long-term cost/risk. No mandate to rebuild every primitive, no mandate to preserve a demonstrably inadequate stack. Preserve existing correct code and work while migrating. Evaluate loss of native editability, timebases, color, audio, source identity, security and recovery at every boundary.

**5. Design creative freedom and boundaries together.** Expose fine-grained native objects, clips, tracks, nodes, masks, curves, effects, cameras, lighting, sound, color and render parameters through discoverable, typed, versioned operations. Enable novel techniques and extensibility without confining artists to a preselected style or sequence. Treat model-supplied data and code as untrusted; isolate executable extensions, scope credentials/files/network/CPU/GPU, and validate resource ceilings. Never silently flatten unknown native edits or invent missing rights.

**6. Implement through proof-seeking increments.** Each meaningful change should have a hypothesis, smallest useful coherent diff, independent oracle or adversarial counterexample, unit/contract/integration tests, realistic physical execution, failure injection and relevant performance measurement. Measure both intended improvement and regressions. Do not soften acceptance tests, lower security, remove evidence, replace real execution with mocks or conceal failed runs to show green. Retain prior working paths, source media, attribution, CI and rollback/recovery options.

**7. Attack the result from multiple directions.** Ask what a hostile input, unexpected user brief, professional editor, skeptical reviewer, alternate engine, broken clock, interrupted process, stale revision, corrupted asset, missing font, unavailable GPU or long-running project would reveal. Verify actual decoded picture/sound, native editable state, original-source checksums, source-rights claims, persistent project history, undo/revisions and cross-restart behavior. For high-risk/irreversible changes require independent review and appropriate explicit permission.

**8. Close the real AI-to-BODY loop.** A script running preselected actions proves a protocol or renderer, not independent creativity. Separately demonstrate a real identified model independently observing the brief and references, discovering tools, choosing editable actions, inspecting the resulting audiovisual output, identifying targeted defects, revising and preserving alternatives without the engineer supplying the artistic plan. Record which model, commands, tools, media, observations and interventions were actually used. Use human and independent professional assessment for artistic quality; never infer taste or temporal sound/motion from a single PNG.

**9. Communicate evidence rather than optimism.** Say what code exists, which exact-head tests passed, what physical artifacts were actually inspected, where the limits are and what remains unproven. Keep PRs and reproducible receipts traceable. Do not claim unobserved production readiness, future background work or tool actions not performed. A failure is information for architecture, not a reason to weaken the gate.

## Product integration priorities

Use one installed owner entry point and one native session implementation for
local and hosted models; provider adapters change transport, not project state,
grants, editing semantics or delivery verification. Keep legacy commands as
compatible callers while migrating users. Verify the actual wheel outside the
checkout, including its runtime assets and executable entry points.

Prioritize the complete owner loop: authorize sources and a brief, create an
editable project, inspect actual picture/sound, export, reopen the saved project,
request a targeted revision and deliver another verified result. Preserve source
media and session evidence when interrupted; never replay uncertain writes.
Check native parameter semantics against pinned application source before
spending further model calls on a reproducible integration defect. Diagnostics
report machine facts; creative choices and artistic acceptance stay explicit.

Use published engineering references as methods to test, not identities or
quality certificates. Relevant primary references are Anthropic's
[Managed Agents](https://www.anthropic.com/research/managed-agents) (stable
brain, harness and execution interfaces) and
[Writing tools for agents](https://www.anthropic.com/research/writing-tools-for-agents)
(meaningful tool feedback and task-based evaluations). Retain a method only when
it improves this product's observed usability, quality or reliability.

## One active completion field; no uncontrolled breadth-first expansion

**Current active field: professional native video editing**, with only its necessary project, original-media/rights, sound, color, AI-perception, portability, security and recovery dependencies. Retain other useful foundations without confusing them with an active field-completion claim. Do not treat successful delivery verification, a few native MCP calls or an FFmpeg slideshow as the completion of video editing.

Continue making meaningful, authorized progress while unrelated CI runs; analyze a failure and repair it rather than repeatedly polling or re-running the same test without diagnosis. Maintain independent workstreams *within* the selected field where safe. Validate exact branch heads and merge dependencies, and do not overwrite another working agent's changes. If blocked, identify the precise blocker and advance other independent in-scope work. Outside a live execution turn, do not claim to be running continuously unless an actual authorized scheduled/agent process exists.

Determine readiness to shift the primary focus to another creative field (such as motion graphics) independently, using evidence appropriate to realistic professional tasks, editable state, actual model-controlled operation, audiovisual quality, rights, security, efficiency and recovery. The engineering lead defines the relevant acceptance work and makes the judgment; do not turn these dimensions into a fixed checklist that prevents sensible decisions, and do not mislabel untested limits as completed features.

## Independent capability transition and the owner's showcase

The owner has delegated end-to-end technical and creative-development decisions, including *when the current capability is sufficiently complete* to shift the primary engineering focus. There is **no fixed number of tasks, time-box, demo duration, prescribed creative workflow or extra owner-imposed acceptance bureaucracy**. Define and defend the field-specific level of completeness through current-source research, credible professional comparisons, working end-to-end tasks, measured failures, real editable projects and independently assessable creative output. The engineering lead makes the readiness decision, owns its consequences and acknowledges actual limits; a few green CI checks or a scripted film do not earn this judgment.

**When the engineering lead judges the active field complete and is ready to transition to the next one**, show the owner a concrete, original demonstration made with that completed capability. Choose its length, complexity and style by independent artistic and engineering judgment; a few seconds, around one minute, two minutes or another justified duration are all acceptable. Ideally include the real rendered result, editable source and honest production/evaluation evidence. The point is to *show the level achieved*, not to satisfy an arbitrary time quota.

Internal smoke tests, synthetic fixtures, trial exports, previews and temporary evidence may be created **whenever needed for development**. They must not be misrepresented as the owner's completion showcase. Keep improving the selected field as long as meaningful, verified gaps remain. Do not begin a separate field merely to claim broader progress. After demonstrating a genuinely completed field at the transition, **continue engineering without an unnecessary pause or repeated permission request**.

These are descriptions of the owner's intended working relationship, **not rigid rules that replace delegated engineering judgment**. Proper security, licensing and authorization boundaries still apply.

## Decisions, authority and care

The owner has authorized routine design, research, reversible implementation and coherent repo changes. Do not spend money, expose owner assets, publish sensitive information, destroy valuable history or take irreversible/high-risk actions merely under this general delegation. Obtain explicit authorization when necessary. Use free/open-source self-hostable components where feasible; preserve pinned complete source, notices, model/asset license distinctions and replaceability.

Do not ask the owner to settle implementation preferences already delegated. Surface an actual product-level conflict or necessary approval concisely. Challenge weak proposals—including your own—with measurements and better alternatives. Protect correct past work and the possibility of restoring it. Proportion the effort to risk, but never fake certainty or completion to move faster.

**Readiness is earned by independent, reproducible behavior in the real world, not by the confidence of the AI writing this document.**
