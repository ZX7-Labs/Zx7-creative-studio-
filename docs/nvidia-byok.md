# NVIDIA BYOK cloud inference (opt-in, development status)

ZX7's default local editor and BODY run without any cloud account. This
adapter does **not** imply a finished public installer, a cloud account
connection wizard or autonomous professional editing. It supplies the same
creative-model decision protocol over NVIDIA's fixed authenticated HTTPS
endpoint, with the existing host-granted BODY native gateway.

## Supported provider

- Endpoint: `https://integrate.api.nvidia.com/v1/chat/completions` (fixed).
- Default catalog candidate: `nvidia/nemotron-3.5-super-vl-120b-a12b`,
  whose [NVIDIA catalog page](https://build.nvidia.com/nvidia/nemotron-3.5-super-vl-120b-a12b)
  currently advertises a free development endpoint and text/image/video input.
  `qwen/qwen3.5-122b-a10b` remains selectable, but its free endpoint
  is marked *deprecated*, so access must be tested per operator account.
- Credential: `NVIDIA_API_KEY`, read at call time from the trusted process
  environment. The key must never appear in a CLI argument, model prompt,
  checked-in file, chat transcript, debug dump, public issue or source archive.
  Do not paste a real key into tests. Rotate keys if exposure is suspected.
- No automatic cloud fallback; no network request in the default local mode.
- The NVIDIA API currently documents chat + images/video and tools, but not
  a guaranteed `response_format` strict JSON-schema parameter. The adapter
  sends a JSON-only prompt and verifies returned JSON locally; this is **not
  server-enforced constrained decoding**. The local/native client rejects
  `--structured-actions` with NVIDIA to avoid a false guarantee.
- All inference text, including user briefs, tool descriptions, source paths,
  and prior responses selected by the controller, is sent to the chosen
  provider when cloud mode is explicitly enabled. **Private media bytes**
  are not sent unless `--allow-cloud-image-upload` is also specified.
  Original audio input has not been validated for this endpoint and is blocked.
- NVIDIA account quotas, rates, reliability and data terms are external to
  ZX7 and must be reviewed before commercial/public rollout. Per-request
  `max_tokens` is bounded; exact billing limits and durable user quotas
  are **not implemented**. Never equate `max_tokens` with cost certainty.

## Connect a trusted development operator

Obtain a key directly from NVIDIA. Configure it privately in the trusted
process environment; avoid shell-history commands containing the literal
secret. A secret manager or terminal session that does not record the key is
preferable. Use a purpose-specific test key and revoke it when finished.

Example commands below deliberately contain **no secret value**. The
`NVIDIA_API_KEY` environment variable must already be configured securely.

To start a BODY brief service:

```sh
zx7-body --workspace-root ./workspace --creative-provider nvidia \
  --creative-model nvidia/nemotron-3.5-super-vl-120b-a12b
```

As before, the service also requires a distinct, privately configured
`ZX7_BODY_API_TOKEN` for local UI/HTTP authentication.

To run a real host-granted native-editor model trial (after separately
installing the pinned native editor and MCP dependencies):

```sh
python engines/velorn/native-model-client.py \
  --provider nvidia --model-id nvidia/nemotron-3.5-super-vl-120b-a12b \
  --source ./third_party/velorn --config /private/editor-config.json \
  --state /private/editor-state --brief-file /private/creative-brief.txt \
  --receipt /private/new-trial-receipt.jsonl --max-turns 8
```

This command cannot upload observed video frames unless the operator adds
`--allow-cloud-image-upload`. Only grant this after verifying the actual
footage, subjects, rights, privacy and NVIDIA's current data terms. Tool
permissions and filesystem roots are still granted by the trusted editor
host, not by the model. Production pricing/usage caps and first-run setup
are future acceptance gates, not available functionality.

## Real API smoke with GitHub Actions

The repository also includes
[`ZX7 NVIDIA API — Manual Credentialed No-Media Smoke`](../.github/workflows/zx7-nvidia-cloud-smoke.yml).
It runs only on **manual dispatch**, never on a code push, pull request or
app installation. It requires a secret named `NVIDIA_API_KEY` added via the
repository's **Settings → Secrets and variables → Actions → New repository
secret**. Do not put the credential in workflow inputs or commit it.

After this workflow is available on the repository default branch, go to
**Actions → ZX7 NVIDIA API — Manual Credentialed No-Media Smoke →
Run workflow** and select the catalog model. The test sends only a synthetic
JSON protocol challenge and reports bounded result metadata, not the key,
response text or private media. The Qwen route may be unavailable if its
deprecated free endpoint cannot serve the operator account.

The development/chat execution environment may have no outgoing network or
DNS. Source-level contract tests can pass there, but **they are not a live API
trial**. No NVIDIA account connectivity, key validity or usage availability
is claimed until an actual successful smoke receipt exists.

## What is verified

Offline tests mock the HTTPS request boundary, token handling, status errors,
JSON decoding, schema mismatch and media opt-in. A successful mocked test
does **not** verify a valid NVIDIA account, actual rate limits, model quality,
native editing revisions, or export quality. To prove those, run a live,
credentialed and permissioned host trial and retain model-independent
editor/export evidence. The development chat and public repository must never
contain or store the actual test key.
