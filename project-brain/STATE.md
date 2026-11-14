# ZX7 — current engineering STATE

**Verified main · 2026-11-14 IST:** `441f27503785c765f6da40bff1361b7fcedf33b6`. [#332](https://github.com/ZX7-Labs/Zx7-creative-studio-/pull/332) merged at `840f782c03fe1bfc468b7191b1e94403f251f438`; [#333](https://github.com/ZX7-Labs/Zx7-creative-studio-/pull/333) merged at current head. The previously completed [#330](https://github.com/ZX7-Labs/Zx7-creative-studio-/pull/330) source-native in-flight X11 edit and pre-rename interrupted-write proof remains integrated. The historical [STATUS](../docs/continuity/STATUS.md) is an archive, **not** another current checkpoint.

## Integrated, source-verified G1 native project safety

**Scope: technical native video production infrastructure, not field C or A–L professional acceptance.**

- **Concurrent independently running cooperative OS writers:** #332 head `aee506802c815d2cd86f743676763ac312c0a58f` passed **16/16 exact-head technical workflows**. Real installed Linux Electron/X11 [#43496849540](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/43496849540) succeeded twice on the same source head. An independent OS writer committed a new actual `.comfystudio` byte SHA while the original GUI had stale unsaved state. Its save and real GUI close were refused rather than overwriting that commit or losing the live state. A *fresh* Electron explicitly reopened and then saved a new version, retaining external metadata and original video/audio SHA, editable clips and keyframes. Independent native Linux `flock`/source-hydration/symlink/process-death tests and physical A/V/reopen passed. [Full MLT #43496849656](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/43496849656) and [original video renderer #43496849631](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/43496849631) passed. No downloadable native cross-process archive was uploaded; use source-pinned CI jobs/logs as receipts.
- **Owner-installable, separate Linux native runtime:** #333 exact head `88718fefc84ae9b875944d0932ae55ac586b9bd8` passed **6/6 exact-head workflows**, including actual Ubuntu 24.04 source installation [#43502720838](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/43502720838): separate fresh-prefix `--cross-process-collaboration` profile, exact approved native source SHA `4d12ecd8017fecba478798671af7ee6aa9cc9ad4`, installed pinned Node 24, Linux lock and source-hydration tests, refusal to replace existing install, sandboxed Electron X11 selected-image decoding, installed owner CLI/native video create/export/reopen and unchanged upstream sources. Stable/default/scene/editorial profiles remain unchanged. The opt-in installed source remains cooperative-writer, same-host Linux scope; a second *simultaneous GUI application* was **not** physically proven.
- **Negative evidence retained:** #332 [earlier native #43491085776](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/43491085776) failed (native revision refusal, then display mismatch); an old native collaboration attempt initially failed and passed a same-head rerun. #333 [installer #43499152565](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/43499152565) failed nonblocking lock expectation using the runner Node (root cause of its runner-dependent outcome not proven); [#43502301778](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/43502301778) then passed pinned installed Node lock tests but failed physical owner CLI discovery without the installed `bin` on PATH. Corrected installer head passed both stages without loosening source/write refusal assertions. Some post-merge main workflows are independently running; their status is not inferred from PR CI.

## In-flight G1 editorial implementation (not merged or accepted)

- **Draft [#335](https://github.com/ZX7-Labs/Zx7-creative-studio-/pull/335)**,
  branch `work/g1-loss-aware-native-editorial-20261114`: one pure loss-aware
  native video/audio razor plan with tests, source-overlay on the previously
  verified Linux cross-process CAS child, isolated `--loss-aware-editorial`
  owner install mode, strict host clip-identity and native revision fences,
  and native Electron before/after original-video/audio decoder comparison
  and saved/reopened editability assertions. Legacy native source and GUI
  razor remain unchanged, while unsafe `extract_range` remains BODY guarded.
- **Verified intermediate CI, not final acceptance:** initial test-first
  expected RED [#43543604774](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/43543604774);
  pure tests GREEN [#43543774830](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/43543774830);
  reproducible exact earlier native overlay and tests GREEN
  [#43544302968](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/43544302968);
  repeated edited-animation cut GREEN
  [#43544624665](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/43544624665).
  Original patch header and native CAS insertion errors were reproduced,
  corrected and retained as negative evidence. Later source descriptor and
  actual batch-placement metadata changes **change the deterministic child
  SHA**. The branch's `loss_aware_editorial_revision` lock must be replaced
  with the latest inspected child SHA; fail-closed `--install` refuses a
  mismatched source pin.
- **Still OPEN / blocker:** latest
  [source inspection/Node CI #43546138396](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/43546138396)
  was queued at checkpoint; no latest SHA proof, source-pin update, actual
  installed Electron edited project/reopen, pre/post decoded video+audio
  equality, or fresh Ubuntu owner installation has passed at this checkpoint.
  Do NOT merge, mark ready, or claim this slice complete until those physical
  gates pass. No paid inference or private owner media sent.
- **Continuation without replanning:** read #335 latest head and job logs;
  obtain final clean child SHA from inspect, pin it; run/examine physical
  Electron and fresh-owner installation workflows, correct real failures
  without softening tests, merge once checked. Next coherent editorial area:
  native GUI/MCP razor parity and genuinely loss-aware ripple/extract with
  timed effect/transition source semantics, then actual replaceable-Brain
  source-informed editing, independent perceptual evaluation and A–L work.

## Next highest-value coherent capability: professional native editorial fidelity and actual creative control

Continue **field C (native video editing) with dependencies A/B/F/G/I/J/K**, not another generic framework or a collection of CI-only patches. Initial concrete product defect: [upstream native razor/split loses right-side effects/keyframes](https://github.com/ZX7-Labs/Zx7-creative-studio-/issues/72); the current BODY appropriately refuses enhanced clips instead of damaging them. Audit linked audio, reverse/retime, transitions, curve semantics and native undo; implement source-pinned loss-aware, physically verified edits across an actual edited source timeline, not a blind unsafe wrapper. Prove before/after decoded picture/audio, editable saved native project/reopen, affected object identities, precise timing, negative/rollback cases, and installed owner entry point. Do not claim lossless equivalence without checking actual native renderer curves and original media.

**Full G1 exit remains OPEN:** a genuine replaceable model independently chooses nontrivial original video **and sound** editing, observes real meaningful time-aligned picture/audio, selects and persists an improvement, produces two independently verified conformant outputs, survives human interference without lost work, and earns independent professional artistic/user/security/rights review. The former genuine NVIDIA and weak local CPU trials failed; model autonomy, semantic listening and artistic quality remain **UNPROVEN**. Owner explicitly defers NVIDIA API use in current offline/native work; no paid inference, private owner-media egress or public launch is authorized.

## Operating guardrails

Read [AGENTS](../AGENTS.md), [CAPABILITIES](../CAPABILITIES.md), [ENGINEERING_STANDARD](../ENGINEERING_STANDARD.md), [BRIEF](BRIEF.md), [DECISIONS](DECISIONS.md), [RISKS](RISKS.md), the [Master Plan](../docs/ZX7_CREATIVE_STUDIO_MASTER_PLAN.md), [F01–F14](EVIDENCE/2026-11-12-G0-COVERAGE.md) and [evidence index](EVIDENCE/INDEX.md). One authoritatively saved native editor state, one host-granted model-independent BODY, preserved original media/rights, no uncertain-write replay, local-first FOSS outcome. Scripted checks, actual neural autonomy and independent artistic acceptance are **different** evidence classes. Refresh PR heads, CI and artifacts each session.
