# Project Brain — where to read and update

Start at [AGENTS](../AGENTS.md). This is durable engineering memory, not another product specification.

| Need | Single owner |
|---|---|
| Founder intent/consent changed | [BRIEF](BRIEF.md) |
| Current status / next action / working branch | [STATE](STATE.md) |
| Typed implementation, failures, gates, source IDs | [EXECUTION_LEDGER](EXECUTION_LEDGER.json), bound to STATE |
| Exact evidence and original artifacts | [EVIDENCE/INDEX](EVIDENCE/INDEX.md) |
| Whole-product audit and completion strategy | [28 November independent audit](EVIDENCE/2026-11-28-INDEPENDENT-PRODUCT-AUDIT.md) |
| Causal failure and retest distinction | [EVIDENCE/FAILURE_REGISTER](EVIDENCE/FAILURE_REGISTER.md) |
| New architecture decision | [DECISIONS](DECISIONS.md) |
| Active risk and falsifiable exit | [RISKS](RISKS.md) |
| Source owners / architecture | [PROJECT_MAP](PROJECT_MAP.md) |
| Original product contract and document roles | [DOCUMENT_MAP](../docs/DOCUMENT_MAP.md) |

Refresh canonical branch, main, relevant PRs and runs. At a meaningful checkpoint **replace** compact STATE, update typed ledger and set exact `LEDGER_GIT_BLOB` in the same commit. Link evidence instead of repeating logs. Keep earlier snapshots and negative results in Git. Run `python project-brain/check.py` and `python -m unittest discover -s project-brain -p 'test_check.py'`.

Never copy private uploads, prompts, credentials or scratch archives into public Git. Artifacts expire. Before retiring branches prove recoverability of exact tips and evaluate distinct useful behavior. Ancestry and green CI do not certify semantic integration or professional quality. [Prior full navigation](https://github.com/ZX7-Labs/Zx7-creative-studio-/blob/766dd9d0076c442f364124b23d1c04412581d184/project-brain/README.md).
