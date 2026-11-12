# AI-native creative perception: source-checked research and falsifiable trial

**Research checkpoint:** 13 November 2026 IST. **Status:** research synthesis and experimental contract ONLY; no new model trial, feature, benchmark win or approved architecture. Derived from [the existing master design](../../docs/ZX7_CREATIVE_STUDIO_MASTER_PLAN.md), especially §§4–6, G1/G2 and its source atlas. This note does not create another state owner, universal format, renderer, inference service or mandatory model architecture.

## Founder question and existing commitment

The question is NOT “how can the model move a mouse like a person?” It is: what perceptual **interface** allows a replaceable AI to understand and operate the creative world as accurately as possible using its own strengths? A professional human combines selective attention, visual/acoustic observations, learned craft, immediate motor feedback and reversible correction. The computer counterpart need not imitate the hand: code/curves/graphs can precisely specify changes, but do not themselves certify what an actual video *looks* like, what a soundtrack *means*, or whether it feels intentional.

The repo **already specifies** AI-perspective-first controls, perceptual evidence, typed native actions, source/render verification, human revision protection, an adaptive-medium hypothesis and a G2 native/code/hybrid A/B/C comparison. Do not rename or reimplement these as discoveries. The founder's private Vision & Standards v1.0 prioritizes originality, then production-strength architecture, then disciplined UX, then honestly measured value. No private founder PDF or media belongs in public Git.

## External research checked (decision-relevant, not reproduced here)

| Domain | Source and observation | Implication for ZX7; unresolved limit |
|---|---|---|
| Active perception and selective evidence | [OmniAgent, ICML 2026](https://proceedings.mlr.press/v306/xing26g.html) describes a POMDP-style observation/thought/action loop selecting video/audio evidence on demand; author-reported multi-benchmark advantages. [Active Visual Perception review, Sensors 2026](https://www.mdpi.com/1424-8220/26/20/6544) analyzes task-dependent evidence need, sensing action and acquisition cost. | Test task-targeted model-requested probes, *not* a required omni-modal 7B training architecture. Its results do not establish creative-editing success or portability to a different Brain. |
| Embodied thinking vs executable control | [Google Code as Policies](https://code-as-policies.github.io/) shows generated programs combining geometric reasoning, perception APIs and control primitives; [Gemini Robotics 1.5](https://deepmind.google/en/models/gemini-robotics/gemini-robotics/) separates multimodal reasoning and robot actions. | Typed or sandboxed code can be a high-precision instrument. Creative BODY remains the native writer; model-supplied programs are untrusted and bounded. A robot analogy does not prove a creative model can judge a film. |
| Spatial/temporal source truth | [OpenUSD time values](https://openusd.org/release/user_guides/time_and_animated_values.html) distinguishes sampled values from editable animation splines. [Video-MME-Logical, EMNLP 2026](https://aclanthology.org/2026.findings-emnlp.423/) isolates temporal state/order/dynamic spatial reasoning failures. | Expose exact editable native objects, transforms, timebase and state transitions **alongside** meaningful timed visual evidence; do not replace curves with an opaque numerical vector or a screenshot. |
| Acoustic grounding | [CLAP, Microsoft Research](https://www.microsoft.com/en-us/research/publication/clap-learning-audio-concepts-from-natural-language-supervision/) learns a language–audio contrastive space. [HalluAudio, ACL 2026](https://aclanthology.org/2026.acl-long.1797/) tests unsupported claims for speech/sounds/music. | Frequency, RMS, spectrum, LUFS and waveform measure signal properties, **not** an audio event's full identity, dialogue intelligibility or emotional meaning. Learned descriptors require a compatible actual model and calibration. |
| High-resolution interface and sampling limits | [ScreenSpot-Pro](https://arxiv.org/abs/2504.07981) shows challenges in high-resolution professional GUI grounding. [Google video API docs](https://ai.google.dev/gemini-api/docs/video-understanding) warn that a one-frame-per-second sampling path misses fast events. | Avoid mandatory GUI automation and single sampled-frame film evaluation. Probe precise intervals and native UI objects when necessary; benchmark the actual provider/setting rather than cross-paper headlines. |
| Professional end-product criterion | [TimelineBench](https://timelinebench.tensortest.com/docs) evaluates realistic video-editing briefs and delivered result, not only tool syntax. | Representation performance is meaningful only if it improves actual editable, technically correct, professionally judged work on held-out tasks. Respect footage rights and inaccessible benchmark packs. |

**Scientific boundary:** A language model has learned distributed internal representations; there is no demonstrated universal readable “neural language” that arbitrary native application code, Fourier numbers or vendor embeddings can be fed into to yield perfect sensory understanding across models. Native numeric state is often *exactly the right representation for precise edits*, but semantics of unobserved picture/sound remain unproven. Treat raw audio/frames, task-grounded structural facts, trained perception and human artistic evaluation as distinct sources of evidence.

## Candidate research hypothesis, NOT a chosen new architecture

**H-PERCEPTION-01:** Under an identical model, rights-cleared brief, pinned native source, granted tools and comparable bounded resource budget, a **model-selected, task-conditioned active observation path** improves the probability of a *correct next creative decision* over fixed snapshot+uniform A/V observations, without losing native editability, rights, semantic calibration, latency/cost discipline or host permissions.

Model can ask *what to inspect next*, e.g. a precise clip interval, original/rendered frames around an occlusion, sampled onset/offset audio, exact shape/keyframe curve and revision-specific before/after. BODY returns only physically supported, bounded, source-identified observations with explicit unknown/coverage; it never manufactures an object label, emotion, licensed status or taste grade.

A conceptual read-only observation request would carry **task question; native project ID/revision; real object/clip ref; original versus rendered source binding; exact rational frame/sample interval; requested modality/precision; byte/time/call budget; provenance and uncertainty**. The host validates these, selects the installed capable reader and returns a typed result. **Not an implemented API/schema**, not a mandate to use a particular detector or train a neural codec, and not another document owner.

## Pre-registered comparison; do not write a medium before evidence

Test **independent observation conditions**, while holding the actual edit path fixed so perception improvements are not confused with action-authority improvements:

| Arm | Model-visible evidence |
|---|---|
| P0 structural baseline | Current trusted native project/object/curve state and ordinary tool response; no fake visual/audio semantics. |
| P1 passive visual baseline | P0 + fixed-rate or fixed-interval original/rendered frame snapshots (temporal coverage logged). |
| P2 passive multimodal baseline | P0 + bounded timed video/audio samples and simple accurate signal/scene measurements; model-compatible only. |
| P3 active candidate | Same available physical modalities and total maximum budget as P2, but the **model chooses** bounded follow-up locations/modality/precision from host-exposed real probes. |

Where a provider cannot consume a modality, mark the comparison **not comparable**; don't pass opaque embedding arrays as if they were intelligible. Test trained audio/vision semantic tools as separate, versioned ablations (P2/P3 + optional compatible specialist), never confuse specialist-vs-baseline improvement with the active-query mechanism. Keep procedural/native/CSF creative expression routes as a **separate G2 A/B/C factor** after the perception effect is isolated.

**Workload coverage:** minimally (1) fast-cut action or cross-shot identity, (2) moving-object mask/occlusion across frames, (3) sound-event versus picture/speech onset and mix suitability, (4) native vector/shape/keyframe motion consistency, later (5) 3D camera/material/light with actual rendered multi-view evidence. Use rights-cleared synthetic or independently permitted media, blind held-out creative briefs, identical model settings/tool and cost ceilings, paired task order and repeated trials where variance matters. First validate probes and physical oracles *offline*; do not make an unconsented paid NVIDIA call.

**Measure separately:** task-grounded perceptual factual correctness (including false positive/unknown); target native object and temporal interval; first-try edit correctness; ability to detect a planted contradictory observation; independently decoded picture/audio improvement and source/native editability; safe rejection of stale human writes; physical semantic A/V grounding; blind calibrated human preference for artistic edits; elapsed time, context tokens, model/tool calls and spend. Track failures and abstention, not just model narration.

**Go:** replicated, attributable improvement in held-out task completion or perceptual correctness with no critical security/native fidelity regression and acceptable added complexity/cost. **Kill/simplify:** P3 offers no meaningful improvement over P2 at matched budgets, makes false confident claims, loses source/state or adds unacceptable operational burden; continue on the simplest proven baseline. A simulated/scripted source experiment is not a real model/art pass.

## Execution ordering and non-goals

1. Preserve current G1 acceptance gate: genuine Brain-selected native video + sound, timed perception, independent actual revision, original custody, human override and professional review; no new code framework substitutes for that.
2. Identify the *first* genuine model failure caused by missing/mis-timed/unsupported observation versus planning, model skill, executor or rendering. Establish physical oracle and one minimal read-only probe using the existing gateway/session, not a second media store.
3. Run the P0/P1/P2/P3 isolation with authorization and exact model/media/source IDs. Compare native-versus-code-versus-hybrid only after perception confounders are understood. Document negatives and reject H-PERCEPTION-01 if it fails.

**Evidence status:** upstream papers/docs inspected 13 Nov 2026; not independently reproduced; ZERO new ZX7 model trials or changed runtime behavior in this record.
