# ZX7 BODY — Full Capability and Acceptance Contract

This is the **enduring product and engineering contract**, not a progress diary,
creative-model prompt, chat handoff or certificate of readiness. The companion
[ENGINEERING_STANDARD.md](ENGINEERING_STANDARD.md) defines the implementer's
independent working method, delegated readiness decision and demonstration at a capability transition. Read it with
`AGENTS.md`, `README.md`, real code and the **latest GitHub CI**. Historical
original decisions remain in Git history; this contract preserves their full
scope without treating old claims as current measurements.

## Product and quality standard

One coherent, source-aware, open-source creative working environment that an
**external, replaceable AI brain** can operate like an unusually capable
professional creator: discover, author, inspect, visualize, hear, revise,
compare, undo, preserve and deliver real editable artistic projects. The brain
makes original choices; BODY offers native capability, trusted execution,
accurate physical observation, project memory and legally usable assets.

Do not prescribe art style, scene count, category, duration, language, aspect,
camera, music, palette, transitions, editor, model or creative workflow.
Adaptively compose vetted engines; do not rebuild an inferior clone of
them or expose a thin API façade as a finished field.

The aim is to **exceed present best practice across the full relevant space**:
intelligence, creative originality, technical control, factual fidelity, image
and sound quality, accuracy, security, privacy, safety, robustness, reliability,
recoverability, latency, computational efficiency, cost, memory, performance,
scalability, interoperability, maintainability, adaptability and accessibility.
This is a research ambition, never an earned marketing ranking without external
professional comparisons. The quality of imagination, independent research,
planning, systems architecture, algorithms, design, implementation, testing and
self-criticism must meet the same high bar. Compare leading current and
historical practices and useful ideas from other scientific fields; invent or
combine methods only when evidence shows an improvement.

## Ownership, open-source scope and replaceable extensions

ZX7 BODY is the independently designed software product. Creative models,
plugins and skills are replaceable attachments, not the definition of BODY or
a mandatory vendor service. Integrating mature open-source code does not remove
the need for a coherent ZX7 architecture, project model and control boundary.

The owner's clarified constraint is a free/open-source, self-hostable system:
no paid service or third-party hosted AI API is a required runtime dependency.
Local IPC/HTTP between BODY and an independently running local model or engine
is an internal transport, not a dependency on a hosted service. Keep that
distinction explicit in documentation and discovery.

For adopted software retain accessible complete upstream source at an exact
revision, applicable licenses/notices, any patches and reproducible build
instructions. Decide packaging/vendoring after selection; a package download
or an executable alone does not fulfill the source-availability requirement.
Weights, voices and other assets are separately licensed artifacts and remain
separately managed from public source code. Do not promise their eligibility
from a code repository license or require all optional models to be installed.
An older open-source release is eligible only under its actual license; later
closed or restricted additions do not inherit that permission.

Engineering research may use source hosting, package registries and research
tools to obtain and inspect material. Those tools must not become hidden
runtime requirements of the delivered BODY. Audit actual existing network/model
routes and identify optional external features rather than claiming that all
historical code already conforms.

## Complete A–L capability map (no entire row certified)

Original source contracts specify twelve mutually dependent domains. Existing
paths indicate **partial implementations**, not complete ability. Inspect all
file contents and installed engine availability before claiming any operation.

| Domain | Current foundations to inspect | Required end-to-end proof |
|---|---|---|
| A. Truth, ownership and rights | `media_vault.py`, `body_archive.py`, `body_publication.py` | Owner facts and legal rights, exact SHA custody, source revocation, secure import/relink and preservation under concurrent failure |
| B. Unified editable project/interchange | `film_ir.py`, `body_sequence_otio.py`, `body_mlt_editor.py`, versioned graphs | Loss-aware native/portable multitrack visual and sound project, reversible transformations, no lost metadata/effects/audio, cross-host transfer |
| C. Professional nonlinear video editing | Pinned `third_party/velorn`, `engines/velorn`, `body_editor_mcp.py`; preserved `body_mlt_*`, `precision_retime.py`, `composite_mix.py` | Exact rational picture/audio clocks, arbitrary art-directed multitrack cuts, trims, ripple/roll/slip/slide, speed curves, transitions, layered keyframes, sound sync, true undo |
| D. Graphic/vector/photo/type and 2D/2.5D motion | `body_visual_graph.py`, `body_visual_render.py`, `motion_studio/`, `body_planar.py` | Original editable art, masks, roto, tracking, typography, geometry, curves, alpha, filters, compositing and measured pixel/time fidelity |
| E. Native 3D/CGI/VFX/simulation | `body_cgi.py`, `body_motion_project.py`, `body_exr_passes.py`, `blender_scene.py` | Open artist control of objects/materials/lights/cameras/nodes/physics, EXR float passes, real motion and restart, multi-genre professional CGI |
| F. Color, grading and final masters | `body_color_pipeline.py`, `body_aces2_movie.py`, `film_finishing.py` | Explicit image primaries/transfer/alpha, correct OCIO/ACES and scene-linear workflow, 10bit/HDR/SDR cross-engine proof and verified deliverables |
| G. Music, sound, voice and subtitles | `composite_mix.py`, `body_loudness.py`, `voice_lab/`, voice contracts | Authenticated dialogue/music/SFX, voice legality/identity, stems and channels, sample-accurate gain/mix/retime, LUFS/true peak and actual listening |
| H. Original footage and media generation | `comfy_video_runtime.py`, `generative_video_providers.py` | Actually installed licensed models and weights, hardware, consistent shots, physical decoded results and creative quality; no assumed free GPU |
| I. Orchestration and reliability | `body_integration.py`, `body_signal.py`, `durable_graph.py`, `body_service.py` | Typed permissioned discovery, dynamic resource dispatch, partial invalidation, provenance, concurrency, transaction safety, crash/cross-host recovery |
| J. Perception and targeted self-correction | `body_observation.py`, `body_review_compare.py`, `body_creative_session.py` | Genuine encoded A/V evidence, real semantic/temporal review and independently judged, meaningful visual/story/audio repairs; scripted-model tests are NOT autonomous creative proof |
| K. Owner/mobile UX, hosting and privacy | `body_mobile.py`, `body_client.py`, `body_verified_delivery.py` | Real Android/off-LAN authenticated HTTPS, private secure upload/preview/revise/download, backups, cost control and accessibility |
| L. Independent professional release quality | End-to-end output + human critique, not merely source files | Multiple materially different full films/designs independently evaluated for creativity, polish, reliability, legality and usability |

**Zero complete-field or beyond-world-best claims are justified merely by the
presence of these files or by passing tests of narrow operations.** Separate
implementation status, installed host availability, technical measurement,
independent creative acceptance and support of realistic workloads.

## Non-negotiable design and verification laws

1. **Recover all capabilities and original goals before choosing the next fix.**
   Read primary source files, available historical decisions, the entire
   relevant code path, current PRs and exact-head CI. Do not mistake source
   history for an active branch, or a document for working software.
2. **One unified project, many specialist engines.** MLT, FFmpeg, OTIO,
   Blender, Inkscape, OCIO, audio and vetted model adapters exchange explicit
   media provenance, rational time, coordinates, color, audio and edit intent.
   Conversion must report loss or fail closed.
3. **Every creative action is revisable and inspectable.** New versions never
   replace previous originals. The AI can operate the actual state, see/hear
   real output, diagnose a precise defect, edit it and prove a meaningful change.
4. **Distinguish host limits from creative limits.** Practical time, RAM, VRAM,
   safety and source budgets are measured, explicit and extensible. Do not
   hardcode examples, demo templates, fixed effects, scene counts or processing
   sequences as universal product behavior.
5. **Model intent has no unrestricted host authority.** Model-authored procedural
   code, shaders and native parameters may enable original techniques, but require
   validated contracts and isolated execution with explicit filesystem, network,
   CPU/GPU and time limits. Do not execute arbitrary Python/shell/native plugin/XML
   in a trusted host merely because model text requests it. Do not fabricate rights,
   disclose secrets, or infer authorization for paid compute or network exposure.
6. **Use full-stack evidence.** Test real source hashes, decoded frames/audio,
   exact clocks, sample/opacity/color behavior, failure injection, malicious
   inputs, long projects, installed wheel, true process death, host variation,
   resource performance and external editor/human quality. No weakening failed
   acceptance assertions or fake background work.
7. **Preserve valuable code and history.** Make cohesive isolated changes,
   correct existing defects rather than parallel copies, run focused plus
   adversarial full regressions, require exact-commit green CI, then merge.
   Preserve licenses, owner media, approved voices, source files and previous
   creative work; public repository contains source/essential docs, not media
   samples or personal assets.

## Implementation focus after research and design

**Whole-studio integration across A–L is active (owner clarification, 26 November 2026).** Video/NLE is one important workload, not a prerequisite that blocks graphics, motion, CGI/3D, VFX, photography, typography, color or sound. Resolve shared and domain-specific dependencies by measured evidence. Reuse existing implementation and tests before adding work. Judge completion independently for each field from real editable native projects, physically verified outputs, model-controlled operation, rights, security, usability and professional quality; showcase completed capabilities with concrete original work, not scripted fixtures. Continue other independent work without unnecessary permission pauses.

At the end of each engineering cycle, prefer concrete verified work and an
honest unresolved gate over progress prose. Keep durable intent in this contract,
usage in README and agent entry guidance in AGENTS.md. Use Git history, issues,
PRs and reproducible evidence for implementation status. Avoid repeated dated
handoffs, transcripts and competing instruction documents.

## Astra: owner's complete mandate and current stage

This section is addressed to Astra as the independent research lead, chief
architect and chief engineer assisting the owner of ZX7 Studio. Astra is the
engineering collaborator reading this repository; the deployed creative brain
must remain independently replaceable. Do not make Astra or any one vendor a
runtime dependency merely because this brief addresses that model.

The owner's ambition is: **the world's present best is the starting point for
our thinking, not its ceiling.** This expresses a demanding engineering
standard. It does not prove that a prompt changes intelligence, that the project
already surpasses competitors, or that tradeoffs and future defects disappear.
Earn conclusions through evidence; challenge your own assumptions, preserve
what works, and invent only where an identifiable benefit justifies it.

**Current instruction: choose and integrate complete capable open-source
applications instead of recreating their capabilities from primitives.** The
owner superseded the earlier research-only freeze and authorized implementation,
redesign and repository updates. Make independent source-backed decisions;
the owner's examples describe breadth, not a required library or fixed pipeline.
Integrate the full studio in dependency order; do not make one field a mandatory serial prerequisite for unrelated work. A working short export is technical
evidence, not professional field completion or autonomous creative acceptance.

### 1. The actual product and its users

Build a unified creative production system whose owner can state a brief in
ordinary language, including Hindi or Hinglish where supported, provide
references or original material, request revisions and receive real work.
The system should serve professional creative production, including advertising
and agency work, without being locked to that genre. A film, graphic, thumbnail,
animation, product render or sound project is an output of shared capabilities.

The central relationship is brain and body. The brain interprets the brief,
researches where appropriate, understands references, invents the direction,
plans and adapts its work, chooses tools and parameters, and judges results.
BODY supplies controllable instruments, editable state, execution, sensing,
history, recovery and delivery. The owner should not have to author a complete
scene JSON, prewrite every tool command or manually rescue normal operations.

The project must support both existing-media editing and creating new material.
Procedural graphics, native 3D and generative models are complementary means.
A generated clip alone does not fulfill editable video production; a timeline
alone does not fulfill original generation. Preserve both capabilities.

### 2. What independent creative control means

The brain must be able to discover an installed engine's relevant operations,
inspect current project state and choose fine details instead of receiving only
a small menu of canned effects. Examples of required expressive scope:

- Editorial: source and take selection; source in/out; rational timebases; clip
  positioning; multiple picture/audio lanes; split, trim, ripple, roll, slip and
  slide; gaps, nested sequences and synchronization; transitions; constant and
  varying speed, reversals and freezes where supported; revisable effect order.
- Animation: keyframes, interpolation and tangent/curve control; spatial paths,
  timing, acceleration, holds, easing, hierarchy, constraints, opacity,
  transforms, masks and parameter animation. Do not restrict art to a fixed
  number of scenes or a universal duration.
- Graphics: editable text, shaping, fonts, line breaks, layout, vector geometry,
  layers, paint/photo operations, masks, blending, shadows, gradients, textures
  and transparent output; typography must render correctly at final resolution.
- 3D: objects and geometry; rigs, bones, poses, actions and animation curves;
  materials, textures and nodes; lighting, shadows, camera and lenses, focus,
  depth of field, simulation parameters/caches and render passes.
- VFX: tracking, roto, segmentation, mattes, keying, compositing graphs,
  premultiplied/straight alpha, scene-linear operations, multi-pass composition,
  integration of rendered elements into footage and editable correction.
- Audio: voice delivery and timing, music/SFX selection or creation, tracks,
  channels, stems, placement, gain curves, fades, ducking, effects, retiming,
  synchronization and finishing; dialogue, Hindi/Hinglish and music require
  actual listening and language-specific evaluation.
- Delivery: preview and final settings; codec/container/resolution/frame rate;
  color transforms, HDR/SDR where supported; captions; project archives and
  native/portable editable exports with explicit losses.

These examples define breadth, not a frozen method whitelist. The architecture
must allow new vetted operations and new artistic techniques. Necessary
precision, resource and security contracts are engineering constraints, not
a house style. Distinguish unavailable tools from artistic impossibility.

### 3. The required closed creative loop

A successful workflow lets the brain inspect the project and available
resources, choose a next action, execute it, inspect real consequences, revise
selected parts and retain the alternatives. Planning may change after feedback.
Do not force every project through one linear script-to-scenes pipeline.

Observation must refer to actual encoded output or native project state.
A contact sheet supports some picture judgments; it does not establish motion,
pacing, sound quality or audiovisual coherence. A transcript does not prove
prosody or music balance. Use appropriate timed frames, continuous segments,
audio, waveforms and native state, with their limitations exposed to the model.

A repair must identify the issue, change the relevant controllable state and
produce evidence that the intended improvement happened without losing other
accepted work. Preserve original sources, editability, undo/redo, versions,
ownership and reproducible execution receipts. Re-render only invalidated
dependencies where correct, while verifying that cached outputs remain valid.

### 4. Research every field, with the right comparisons

Treat the A–L map above as the full scope. Investigate complete creative
systems, domain engines, libraries, execution frameworks, AI brains, perception
models, generative models and inference optimizations. Label which kind each
candidate is. They solve different parts of the problem; comparing their names
as though all were interchangeable tools produces misleading conclusions.

For each important capability:

1. Define real professional tasks and required granular controls before ranking.
2. Find leading current approaches through primary documentation, source,
   papers, model cards, releases and reproducible evaluations. Record the date,
   exact identity/version and evidence limits. Search beyond famous projects.
3. Read how the relevant implementation works, not only its README or demo.
   Check control surfaces, data models, precision, persistence, failure modes
   and implementation restrictions. Resolve contradictory documentation/code.
4. Trace smaller derivatives and alternate designs: selective dependencies,
   quantization, distillation, pruning, sparse attention, caching, offloading,
   CPU/ONNX/native paths, real-time renderers and task-specific engines.
5. Compare on the same task and usable output quality. Separate upstream claims,
   independent published results and our own measurements. Do not convert stars,
   release recency, tool counts or test counts into quality rankings.
6. Investigate commercial leaders as reference workflows where useful through
   public information and lawful use. The deployable preference is free/open
   source; paid products are not automatically eligible building blocks.
7. Decide adopt, integrate, adapt/fork, defer or build. Explain which measured gap
   each decision addresses and what dependency/maintenance burden it creates.

The earlier landscape included MLT, FFmpeg, OTIO, Blender, OCIO, Inkscape,
Krita/GIMP, Gaffer/Natron, HyperFrames, OpenFilm, Motion Canvas, ComfyUI and
multiple generative/perception/audio families. Subsequent exploration included
WanGP, FastVideo, SparkDiffusion and Nunchaku. These are **research leads,
not a frozen approved stack or verified winners**. Verify current upstream
identity and terms again when selecting versions.

Do not claim an exhaustive internet search or an absolute planet-wide winner
from a finite survey. Aim to identify the strongest defensible candidates for
each workload and keep a record of consequential exclusions and unresolved
alternatives. A narrow matched test can settle a narrow claim; it cannot
certify all genres, languages, hardware or future versions.

### 5. Multi-dimensional quality and lightweight design

Evaluate intelligence, capability, creative originality, accuracy, image/sound
quality, security, safety, privacy, reliability, recovery, efficiency,
performance, latency, RAM/VRAM, compute, storage, cost, scalability,
adaptability, verifiability, portability, interoperability, maintainability and
owner usability. Add domain-specific dimensions when they materially matter.

Do not hide an essential failure inside an aggregate score. Required controls,
rights, correctness and acceptable output quality are gates. Among eligible
candidates, compare the tradeoffs and retain non-dominated choices. If quality
and latency conflict, first investigate a better architecture or technique;
if a conflict remains, state it honestly with measurements.

Low parameter count, download size, disk size, peak VRAM, total RAM, startup
time, inference time and end-to-end project cost are different quantities.
CPU offload can lower VRAM while increasing latency and RAM. Fewer diffusion
steps can change adherence or diversity. Proxy previews can diverge from final
output. Distinguish these interventions and evaluate their effect.

Design for lazy loading, resource discovery, safe concurrency, cancellation,
resume, bounded work, cache invalidation and appropriate backend selection.
Do not require every large model to stay loaded. Do not silently degrade a
requested result: report the applicable capability or resource limit and let
the authorized workflow choose an alternative.

### 6. Reuse, source study and hybrid architecture

Study open-source source code and architecture under its actual license.
Prefer mature components where they solve the problem. Reimplement only when
evidence establishes a missing capability, a deployment constraint or a real
benefit. Preserve attribution and distribution obligations. Open weights,
open-source code, an API client and a free hosted quota are different things.

Hybridization is a reasoned option, not a requirement to accumulate engines.
Combine complementary strengths only after accounting for conversion loss,
extra copies, clocks, coordinate systems, color transforms, dependency weight,
failure recovery, observability and maintenance. Compare the hybrid against
the strongest simpler solution.

The existing project's useful code must survive this research. Audit it before
judging it obsolete. Do not empty main, erase history, delete tests, replace
native controls with a narrower demo, or create a second competing system
without a reviewed migration rationale. Some current adapters intentionally
accept narrow subsets; that is not the final scope of the product.

### 7. Architecture and planning deliverables before coding

Prepare one coherent reviewable design that covers:

- Requirements and non-goals, professional workloads, acceptance gates and
  traceability from each A–L domain to its controls and evidence.
- Candidate comparisons and the rationale for reuse versus invention,
  alternatives rejected, remaining uncertainty and benchmark configurations.
- Brain/BODY boundary, typed capability discovery, native escape/extension
  mechanisms with isolation, and model/provider replacement.
- Project/asset identity and ownership, source custody, state/versions,
  timeline/scene/node models, exact time, coordinates, units, color and audio.
- Native subprojects and interchange, editable round trips, preservation of
  unsupported features and an explicit report of lossy conversions.
- Execution graph, transactions, permissions, worker isolation, scheduling,
  caching, cancellation, retries, checkpointing and crash recovery.
- Perception, audiovisual review, targeted revision and criteria for escalating
  uncertainty instead of inventing observations.
- Local-first service and Android/web owner access, authentication, secure
  uploads/previews/downloads, private assets and measured hardware requirements.
- Test strategy, comparative evaluation, packaging and deployment assumptions,
  upgrade/migration risks, dependency licenses and operating costs.
- A dependency-ordered implementation plan with small verifiable increments,
  meaningful field-completion gates and a map of existing work to retain.

Separate owner's requirements from your proposed technical choices. Research
artifacts are not executable capability. If resource access prevents a
necessary experiment, identify the exact unresolved test and its effect on the
decision; do not present the entire research/design as finished.

### 8. Evidence for real autonomy and release acceptance

Disclose which model made the creative decisions, its actual tool access,
which engines ran, which assets were supplied, which outputs it observed and
whether a human or engineering assistant authored a scene plan or intervened.
A scripted fake model is useful for protocol tests and must be labeled as such.
An assistant-authored scene JSON is not evidence of a separate deployed model
independently planning and creating the work.

Run representative original projects with a real connected brain through BODY.
Retain command/state histories and output provenance. Evaluate revision
requests, meaningful undo, reopening, recovery and transfer as well as initial
render. Test physically decoded frames and sound, rational rates, audio sample
clocks, real masks/alpha/color behavior and failure cases.

Professional creative quality requires independently assessable output across
materially different briefs. Technical correctness, model competence and
artistic acceptance are distinct. A six-second demonstration, a successful
MP4 export or passing CI cannot certify an entire creative field.

After research and design, resolve shared and domain-specific dependencies
across A–L and declare a field accepted only on its own evidence. The order of
work is determined by measured dependencies, not a mandatory first field. No honest engineering process can promise that no future defect or
revision will ever be needed; the requirement is rigorous completion against
the full agreed gate, not knowingly leaving a prototype disguised as finished.

### 9. Security, privacy, rights and honest resource use

Keep private media, credentials, account data and generated showcase videos
out of the public source repository. Preserve owner originals and accepted
artifacts. Use only licensed material and authorized voices; inspect code,
weights, fonts, sounds and datasets separately where relevant.

Treat imported text/assets and tool output as untrusted data. Generated code
must not gain the host's unrestricted privileges. Protect against path
traversal, unsafe archives, malicious SVG/HTML/scripts, secret access, unwanted
network activity and resource exhaustion. Security must support expressive
creative work through sound boundaries rather than reducing it to presets.

Prefer free/open-source resources and low operating costs. Verify plugin
connection, quotas and pricing instead of equating installation with unlimited
free use. Suggest a missing useful integration when authorized and continue
independent work that does not need it. Do not spend money, create public
exposure or assume free GPU resources merely to keep a demo moving.

### 10. How Astra should work with the owner

The owner has delegated routine technical choices and expects sustained
independent work. Recover available project context yourself; do not repeatedly
ask what the product is, how good it should be or whether you should continue.
Make justified decisions, test assumptions and challenge a weak direction
respectfully even when it was suggested by the owner.

Use brief progress updates when useful and a consolidated verified result.
Do not stop after every search, status message or successful narrow test.
Do not promise invisible work after a turn ends or substitute reminders and
scheduled automations for execution. State a genuine blocker precisely and
continue independent authorized work where possible.

Be transparent about access: project memory is not guaranteed verbatim access
to every earlier chat; a file's existence is not proof of its contents; a
historical commit or CI result is not current state. Inspect the actual source
and exact commit before consequential changes. Preserve correct work and do
not claim tests, listening, rendering, deployment or production readiness that
did not actually occur.

This contract preserves the owner's intent so a future Astra session can start
from the project itself. It is an engineering brief for the collaborator,
not an MD-file substitute for the deployed system's creative intelligence.
