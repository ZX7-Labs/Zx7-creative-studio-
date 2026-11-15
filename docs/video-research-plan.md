# Video foundation research and implementation plan

> **Historical video-specific research/implementation plan, not today's task board.** The underlying product aim and relevant source research are retained; later implementations may already cover individual proposals. Read the [single fixed build crosswalk](BUILD_BLUEPRINT.md), [current STATE](../project-brain/STATE.md) and [evidence ledger](../project-brain/EXECUTION_LEDGER.json) before selecting work. Do not restart old R1–R4/P1–P5 or repeat a passed physical check solely because this early plan says so.

**Goal:** Make native video editing and its necessary project, source, audio,
color, reliability and review dependencies a coherent professional capability.

**Architecture:** Retain the source/rights store, durable execution and useful
native integrations. Introduce loss-aware native project coordination and exact
boundary contracts without flattening every engine into a universal scene JSON.

**Stack:** Complete pinned Velorn application attached to the existing Python
>=3.11 BODY catalog through local MCP. Preserve useful MLT, FFmpeg, OTIO and
Blender routes. Model runtimes remain independent optional attachments.

**Spec:** [architecture.md](architecture.md), [reuse-research.md](reuse-research.md)
and [CAPABILITIES.md](../CAPABILITIES.md).

## Global constraints

* Use source comparison to select a complete application, then implement and
  verify its actual native workflow. Experiments and technical exports remain
  distinct from professional acceptance.
* Preserve originals, rights, native editable state, existing tests and history.
* No public owner assets, generated showcase films, credentials or model weights
  in source control. Synthetic test fixtures may be generated on demand.
* No paid compute or public deployment is assumed. Real model/human quality
  acceptance is distinct from technical correctness.
* BODY is the independent product; models/plugins/skills are replaceable.
  No paid service or third-party hosted AI API is required at runtime. Keep
  complete accessible pinned engine source, licenses, patches and build recipes.
* Preserve Python >=3.11 and existing tool IDs; schema changes are versioned.
* Do not introduce a second asset store, scheduler or competing instruction file.

## Review focus

* Nonintegral picture/sample relationships: preserve exact duration and report
  boundary quantization, including long NTSC projects and 44.1/48 kHz sources.
* Stale concurrent edits/workers: reject parent conflicts and prevent old
  attempts from publishing after cancellation or lease reassignment.
* Foreign native documents with unknown effects: preserve inert bytes and report
  loss; never silently discard data or execute untrusted extensions.
* Rights revoked between cache lookup and delivery: block reuse/publication
  without losing the historical project or the owner's source originals.
* An image-only critic claiming motion/audio quality: preserve modality and
  observed-interval limits through the real model request and acceptance record.

## Active editor integration

Adopt the complete pinned Velorn application; see the
[selection](reuse-research.md#whole-editor-source-selection) and
[adapter](../engines/velorn/README.md). The first executable slice is native
project creation, asset import, independent video/audio/title tracks, editable
text/keyframes, saved versions, reopen and actual audiovisual export. BODY
preserves native schemas and applies explicit host grants.

Professional completion still requires representative client workloads, actual
audiovisual model evaluation, project/restart recovery, isolation and packaging,
codec/font/color/interchange coverage and artistic acceptance. Do not mark these
complete from a short scripted fixture. The R-series below records earlier
foundation work and remaining technical questions; it is not a mandate to
rebuild the editor or postpone justified integration.

## R1: Reproducible sample-clock differential

**Create:** `scripts/research_audio_clock.py`.
**Uses:** `actual_composite_command(plan, workspace, vault, output)` and real
`MediaVault.ingest` with synthetic PCM, plus installed FFmpeg/FFprobe.
**Produces:** JSON receipt with baseline SHA/dirty state, tool versions,
authored source/output sample indices, decoded actual/reference indices,
channel counts, subprocess status and explicit scope.

- [x] Generate deterministic isolated impulses; attest their actual bytes.
- [x] Compile the unchanged BODY audio branch, sink its video branch and render
      lossless PCM. Render an independent FFmpeg sample-unit reference.
- [x] Exercise offsets around sample/millisecond boundaries, nonzero source
      trims, mono/stereo and 44.1/48 kHz inputs. Record mismatches; a mismatch is
      a research result, not a reason to adjust the oracle.
- [x] Fail the probe on missing tools, bad decode or reference disagreement;
      distinguish successful measurement of a BODY defect from conformance.
- [x] Commit the probe and compact synthetic results; rerun from a clean checkout.

Local first matrix: 108 cases, 16 matching, 56 decoded timing mismatches, 36
BODY command rejections; largest observed decoded offset 24 samples at 48 kHz.
Small float source trims were serialized as scientific notation rejected by
FFmpeg's duration parser. This is baseline defect evidence, not a fixed runtime.
The committed workflow repeats the probes on actual Ubuntu MLT/FFmpeg and
uploads receipts. A green research workflow means measurement completed;
inspect its conformance fields before making any product claim.

## R2: Native project and renderer comparison

**Existing paths:** `body_mlt_editor.py`, `body_mlt_render.py`,
`body_mlt_roundtrip.py`, `body_sequence_otio.py`, `composite_mix.py`, their tests.
**Produces:** matched workload receipts, loss reports and selected route rationale.

- [x] Make actual MLT available on an authorized execution host without changing
      product contracts. Record binary/plugin/build versions and resources.
- [ ] Use identical synthetic/source-attested assets and editorial intent for
      native MLT and FFmpeg: three picture layers, independently placed sound,
      gaps, trim/move/undo, gain/pan and effects. Include 30000/1001 and long
      timeline positions. Measure decoded source frames, sample placement,
      quality differences, time and peak memory.
- [ ] Compare native OTIO preservation of nested tracks/metadata with the strict
      existing ZX7 bridge; its deliberate refusals must remain explicit.
- [ ] Reopen native files, repeat one local revision and compare with a clean
      render. Reject unexplained frame/audio/color differences.
- [ ] Update the architecture only when these results change a decision; retain
      both native projects and old tool compatibility.

Completed initial subset: actual MLT 7.22.0 and FFmpeg 6.1.1 on Ubuntu 24.04,
three opaque tracks at 12fps, one native trim/move revision and exact native
reopen. Both baselines selected 12/12 source frames; the revised MLT output
selected 12/12 and FFmpeg 11/12. The broader R2 tasks above remain unchecked.
The optional activation probe changes only one predicate bound by one ULP;
it is diagnostic, not a product remedy or approved epsilon policy.

## R3: Isolation and protocol research

**Existing paths:** `body_plugins.py`, `registry.py`, `body_motion_project.py`,
`body_creative_session.py`, `body_service.py`.
**Produces:** actual host isolation conformance and a narrow versioned protocol spec.

- [ ] Verify read-only inputs, denied secrets/network, bounded memory/disk/process
      count, cancellation and entire process-tree termination on the target host.
- [ ] Demonstrate path/URL/zip and native-file attacks cannot cross the boundary;
      do not call trusted Python plugins sandboxed.
- [ ] Specify capability descriptors, revision preconditions, loss reports and
      modality-aware observations using examples from the R1/R2 workloads.
- [x] Assess whether existing publication/leases can implement multi-artifact
      commits and stale-worker fencing without a second coordinator.

Assessment: retain the current SQLite owner/input checks and publication
journal, but bind the changing admitted attempt to publication/head promotion.
The current publication context does not carry the lease owner. The architecture
records this gap and proposed protocol fields; no concurrent-head safety or
implemented protocol claim follows from this source assessment.

Current-host preliminary result: a fixed `bwrap` profile launching only
`/usr/bin/true` with isolated user/PID/network namespaces failed with a denied
NETLINK_ROUTE socket. Full isolation is unverified. Keep arbitrary-code execution
disabled on this host; do not weaken the profile just to pass the launch.

`scripts/research_worker_isolation.py` now repeats a fixed worker profile on
the actual host: read-only input, allowed output, hidden host file/environment
and separation from a listening host-loopback socket. The `worker-boundaries`
research CI job records availability and checks separately. Even a passed
boundary probe does not establish resource limits, process-tree cancellation,
GPU containment or hostile native-file safety; those R3 gates remain open.

Actual Ubuntu 24.04 CI measurement on `0b59c6852e8ffc879fe3958878bb7ec554a0ce43`
also rejected the requested profile: bubblewrap 0.9.0 reported `Failed RTM_NEWADDR:
Operation not permitted`. The research job completed, but `launch_supported`
and `boundary_checks_passed` are both false. Do not retry by removing network
isolation. The [compact evidence](../research/foundation-evidence.json) retains
the result and run/artifact identities after ephemeral CI files expire.

## R4: Bounded native browser-motion eligibility trial

**Research-only files:** `research/browser-engine/{package.json,package-lock.json,probe.mjs}`.
**Purpose:** Determine whether the actual candidate can seek/repeat simple native
art at integer and NTSC rates before investing in an adapter or a larger craft
comparison. The existing Inkscape renderer supplies an independent vector
geometry reference. This trial does not select an overall animation winner.

- [x] Resolve the published package and inspect its real API/source instead of
      implementing from the README's outdated call signatures.
- [x] Run the locked 0.8.214 package with actual Chrome, Inkscape and FFmpeg;
      compare requested geometry, decoded RGB pixels and repeated out-of-order
      captures at both rates.
- [ ] Record capture path, browser/dependency identities, warnings, limitations
      and actual source/build availability before deciding whether to proceed.

The initial local package install completed but browser download timed out
through that host's proxy; no local browser-render result is claimed. The actual
GitHub Actions [research run](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/40812941034)
on commit `ce59bb8f2c4e9e4fadb748c7f613cab1989bc097` passed its five
acceptance-predicate tests and native Chrome/FFmpeg/Inkscape probe. For this
fixed opaque 64x48 rectangle fixture, all 12 captures across 12 fps and
30000/1001 fps passed rate/frame coverage, expected rectangle geometry,
byte-exact decoded RGB comparison with Inkscape SVG, and out-of-order repeat
checks. Browser logs identify HeadlessChrome 153.0.8010.36, software GL and
screenshot capture. The [run artifact](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/40812941034/artifacts/12870952993)
contains the detailed receipt; the compact verified facts are retained in
[foundation evidence](../research/foundation-evidence.json).

This test's authored HTML implements `window.__hf.seek` itself. The measured
result validates one native capture/callback path, not GSAP/CSS animation
semantics, audio, general artistic quality, arbitrary seeking, or model control.
The pinned upstream source snapshot contains an Apache-2.0 license and
`packages/engine/package.json` version 0.8.214; published-package byte
equivalence to a reproducible source build and all transitive notices/rights
remain unverified. Upstream Chromium runs with `--no-sandbox`; the trusted
fixture cannot certify an untrusted creative-code worker. No inference model
ran. Do not adopt the backend before remaining R4/source and security gates.

## P1: Exact composition clock and audio contract (after research gate)

**Modify:** `composite_mix.py`, `body_document_schemas.py`,
`body_tool_contracts.py`, implementation fingerprints in `body_integration.py`.
**Test:** `test_composite_mix.py`, `test_body_audio_automation.py`, new focused
clock tests and R1 differential against both old and new schema versions.

**Interface decision:** version the composition document; represent authoritative
audio positions/trims/duration in integer samples with an explicit bus rate.
The final schema is chosen from R1/R2 findings, not guessed by an implementer.
Legacy float-second documents retain their documented behavior or undergo an
explicit conversion with quantified residuals; never silently reinterpret them.

- [ ] Write failing decoded-PCM tests for one-sample offsets and trim boundaries,
      44.1/48 kHz, stereo channel identity, resampling and exact bus duration.
- [ ] Confirm failures on the unchanged implementation.
- [ ] Implement the versioned clock conversion at the boundary, not repeated
      float rounding throughout the render pipeline. Preserve source custody.
- [ ] Verify new contract physically, legacy regressions, retime/automation,
      wheel installation and Python 3.11/3.12. Test AAC separately from PCM.
- [ ] Review, require applicable exact-head CI, commit and migrate safely.

## P2: Unified project head and publication

**Retain/extend:** `durable_graph.py`, `body_publication.py`,
`body_project_revision.py`, existing source store and service coordinator.
**New unit if necessary:** `project_manifest.py`, limited to identity/link/head
semantics; it must not encode every engine's artistic properties.

**Interface decision:** edits require expected parent revision and publish a new
immutable manifest/native dependency set. Use existing publication journal for
prepared versus committed reconciliation. Define wire schema in R3 first.

- [ ] Write failing two-editor conflict, stale-worker, process-kill publication,
      revoked-rights-on-cache and cross-host restore tests.
- [ ] Implement compare-and-swap head update and reconcile multi-file artifacts.
- [ ] Prove undo, crash recovery, reopen and retention without source deletion.
- [ ] Commit after focused and existing graph/publication/source tests plus
      required exact-head CI pass.

## P3: Native-rich editorial interchange and revisions

**Extend:** `body_sequence_otio.py`, `body_mlt_*`, asset links and service schemas.
**New unit if justified:** conversion-loss report contract shared by adapters.

- [ ] Write failing multitrack/nested-gap/transition/unknown-effect roundtrip
      tests with exact feature paths and explicit losses.
- [ ] Implement preservation without executing foreign native extensions. Keep
      the strict legacy OTIO route stable and label baked derivatives.
- [ ] Verify split/trim/ripple/roll/slip/slide, linked and independent audio,
      nesting, speed curves, transition handles, curve interpolation and undo
      on physically decoded native results. Unsupported controls remain visible.
- [ ] Compare revisions to clean renders and original source frames; commit
      after full applicable native checks. Do not certify C from P1–P3 alone.

## P4: Actual audiovisual model loop

**Extend:** `body_creative_session.py`, local model adapters,
observation/temporal evidence/review/compare modules.

- [ ] Test that the request truly carries supported A/V evidence and retains
      timing/modality limitations; use protocol fakes only for protocol tests.
- [ ] Implement supported synchronized segment/audio delivery and resumable
      decisions without unrestricted model host authority.
- [ ] Run a real identified model on a brief, observe output, request a specific
      correction and compare results. Disclose every human/assistant intervention.
- [ ] Blindly assess missed defects and regressions; preserve alternatives and
      uncertainty. Never equate a model's self-approval with professional release.

## P5: Full video field acceptance and delivery

**Integrates:** native editing, original sources, clocks/audio, color/EXR,
reliability, owner access and delivery verification.

- [ ] Run materially different briefs: dialogue-led Hindi/Hinglish edit,
      typography/motion advertisement and source-led multitrack narrative. These
      are benchmark tasks, not fixed product styles or duration limits.
- [ ] Evaluate brief adherence, creative originality, typography, motion,
      continuity, pacing, sound, color, polish and required controls separately;
      no average score may hide a failed essential gate.
- [ ] Test targeted revisions, true undo, native reopen/transfer, crash recovery,
      cancellation and realistic long workloads. Retain measured resource/cost
      results and unsupported cases.
- [ ] Complete secure real Android/off-LAN delivery on an authorized deployment;
      verify private assets, backups, restoration and accessible owner controls.
- [ ] Obtain independent craft/owner acceptance and required exact-head release
      CI. Only then record the field's accepted scope; list residual limitations.

## Later dependency-ordered fields

After video acceptance, develop D graphics/type/motion, E CGI/VFX/simulation and
G/H specialist sound/generation according to demonstrated project needs, always
with their A/B/F/I/J/K dependencies. Select painting/compositor/browser/DAW and
model runtimes through matched trials before writing integrations. Update one
coherent design/plan when evidence changes the order; do not generate another
dated handoff or declare all fields complete from engine installation.

## Continuation checkpoint

Read `AGENTS.md`, `CAPABILITIES.md`, these three documents, current Git status,
open PRs and exact-head CI. Start at the first unchecked research task and
verify any existing result before repeating it. Record compact reproducible
evidence in commits; do not rely on a live chat or ephemeral runner filesystem.
