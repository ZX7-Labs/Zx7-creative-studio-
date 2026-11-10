# ZX7 — durable evidence index (positive and negative)

Evidence statements are source-sha/PR/run scoped; hyperlinks to GitHub Actions artifacts may expire independently of this repository.

| Case | Evidence | Outcome / independent limit |
|---|---|---|
| Original Inherit Mode | [Read-only baseline](2026-11-10-INHERIT.md) | Source/pr/CI inventory and initial risk map; no code was built in that mode |
| Pinned desktop + Ubuntu source installer | [#285](https://github.com/ZX7-Labs/Zx7-creative-studio-/pull/285), [#286](https://github.com/ZX7-Labs/Zx7-creative-studio-/pull/286), [installer CI #42694984026](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/42694984026) | Actual source/native installed **scripted** create/export/reopen/revise; not independent AI artwork |
| Qwen 4B full real CPU test | [run #42711402879](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/42711402879), artifact #13722569378, [#288](https://github.com/ZX7-Labs/Zx7-creative-studio-/pull/288) | **FAILED**: 46 decisions, context 9068 > 8192, wrong-profile mostly black 60s MP4, no independently verified observed revision |
| Qwen host-prompt dedup proposal | [#289](https://github.com/ZX7-Labs/Zx7-creative-studio-/pull/289), source-gate [#42751986083](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/42751986083) | Offline context byte reduction 29,231 → 20,771 in failed-turn replay, not tokenizer/brain success. Merge requires all relevant CI/review |
| Historical NVIDIA Super VL | [run #42669603529](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/42669603529), artifact #13698336965 | **FAILED** after 16 decisions: 90s transport timeout, no verified export, no evidence for HTTP 429 rate-limit |
| NVIDIA single-run readiness | [#290](https://github.com/ZX7-Labs/Zx7-creative-studio-/pull/290), merge `3b38b3f411f913736f80cbd9ad402b743c399aca` | Fixed 180s per-call and 1500s outer process bounds, redaction/no-automatic-retry. Relevant offline source and credential tests passed. No genuine quality claim |
| One NVIDIA re-evaluation | [run #42754872382](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/42754872382), source `76104b4f177ad1eb99e0cb17c8fee194d0d6193e` | **IN PROGRESS AT INDEX WRITING**. Treat status as historical and fetch live evidence; do NOT rerun by default |

### Evidence retention rule

On a failed model run retain the earliest causal error category, exact model/provider, exact code SHA, native tool decisions and host-granted outcome journal, independently decoded output profile, original asset digest/custody, export verification result, image/audio observations and edit/revision relationship. Include negative evidence. A passing compiler, schema test or mocked fixture is not proof that an independent creative model delivered usable production work.

When an artifact expires, say its bytes are no longer independently available; never invent fresh media verification. Do not commit private artifacts or auth headers to this index.

| One-shot NVIDIA 48-turn forensic review | [Run #42754872382](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/42754872382), [durable report](2026-11-10-NVIDIA-ONE-SHOT.md), artifact #13735184585 | **FAILED:** real native project, 5 MP4 paths = only 2 SHA-256 hashes; every export 1920×1080 not owner 640×360, 24 fps/6s, no audio; one invalid provider tool-call recovery misclassified by auditor |
| Strict NVIDIA audit parity | [#292](https://github.com/ZX7-Labs/Zx7-creative-studio-/pull/292), merge `c41a705f7e199e57a573ce28ee486b822af5a05d` | Merged bounded no-dispatch provider error audit; source/controller and MLT checks passed; unrelated render check cancelled |
| Host-owned delivery mismatch gate | [#293](https://github.com/ZX7-Labs/Zx7-creative-studio-/pull/293) | **Proposed, not integrated at this evidence snapshot:** source-derived read-only profile check prevents wrong resolution render and preserves generic native flexibility; no new NVIDIA run |
