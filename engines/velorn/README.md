# Velorn whole-editor integration

This directory launches the complete pinned [Velorn source](../../third_party/velorn) and calls its native MCP interface. It does not implement a timeline, compositor, audio mixer or renderer. Upstream commit `b3c02adbd5c0779feb8abf34978299e9502cc0e7`, version 0.3.37; this integration is GPL-3.0-only. Preserve [LICENSE](LICENSE), [NOTICE](NOTICE) and full upstream source with distributions.

## Setup

Use Linux, Node.js/npm, normal Electron runtime libraries, and a desktop display or Xvfb. Run as a regular user with the Electron sandbox enabled.

```sh
git submodule update --init --recursive
cd third_party/velorn
npm ci
npm run build
cd ../..
node --test engines/velorn/client.test.mjs engines/velorn/launcher.test.mjs
python -m unittest studio_next.test_body_editor_client studio_next.test_body_editor_catalog -v
```

When dependencies were installed with `--ignore-scripts`, run the normal Electron, ffmpeg-static and @derhuerst/ffprobe-static install scripts before launching. No model weights, ComfyUI, RIFE or hosted AI API are needed for native editing/export. Upstream `electron:pack`/`electron:build` separately require staged RIFE release inputs; distribution packaging is unresolved.

## Connect a local AI client through standard MCP

Install the optional bridge with `python -m pip install '.[editor]'`. Protocol
negotiation and framing use the pinned [official Python SDK 2.3.0](https://github.com/modelcontextprotocol/python-sdk/tree/v2.3.0).
Copy [editor.example.json](editor.example.json) to a host-owned configuration
file outside the writable project roots, and replace its three absolute paths.
The example explicitly grants 77 local editorial operations from the pinned
source. This is a permission profile, not evidence that all 77 operations passed
production acceptance. Reduce grants for restricted clients. Removing `write`
from `allowed_access` hides and denies mutating operations.

Configure an MCP-capable local AI client to launch this command:

```sh
node /absolute/path/to/zx7/engines/velorn/mcp.mjs \
  --source /absolute/path/to/zx7/third_party/velorn \
  --config /absolute/path/to/host/editor.json \
  --state /absolute/path/to/private-editor-state \
  --python /absolute/path/to/editor-python/bin/python
```

This single process owns the existing editor and the standard stdio MCP bridge.
The `state` directory gets a fresh private profile per connection; projects and
media remain in the configured roots. Add the same display/headless flags below
when needed. Stdout carries only MCP messages. Disconnecting or signalling the
launcher closes its owned processes. Save the native project before disconnect;
this does not promise recovery of an unsaved or interrupted render.

Clients discover unchanged native schemas and choose their own editing values.
Calls validate those schemas and scoped filesystem arguments. Queued cancelled
edits are not applied; an in-flight native call finishes under serialization,
and an uncertain write is never automatically retried. Network/generation,
host-management, nested action plans and batch exports are outside this profile.
Exports require an explicit new `outputPath`; existing project, source and
delivery files are refused as destinations. Opening a project also checks its
primary/legacy native document against the configured project root.
The existing Film IR/mobile creative-session runner remains a separate route;
this connection is for a replaceable MCP-capable brain.

With the example host profile, the additional BODY-owned read-only
`zx7_verify_native_export` tool independently fully decodes a completed
native exported movie (picture and audio), checks its physical hash/identity
against concurrent changes, validates optional target dimensions/duration/audio
and returns an explicitly non-artistic result. It is separately identified
from the 77 granted native controls. Host configuration
`"verify_native_exports": true` opts in; the default is disabled.
Only files in the dedicated authorized output root can be observed; original
project/staging media are intentionally not exposed through this new tool.
After a successful source-bound export proof in the same MCP session,
`zx7_observe_verified_export_frame` can return an actual decoder-produced
PNG image plus a factual source/timestamp receipt to a visual-capable AI client.
The client chooses the requested moment. This is bounded to 768 pixels per
dimension, refuses stale bytes and reports that one selected still does not
establish continuous motion, exact frame presentation PTS, sound quality,
scene-linear/HDR fidelity or artistic acceptance. The additional
`zx7_observe_verified_export_samples` tool accepts **2–4 strictly increasing**
requested timestamps and returns multiple separate genuine decoded PNGs with
per-frame source-bound hash receipts. At most 8 MiB of raw PNG bytes may be
returned in one call. It is a sparse temporal visual observation, **not**
continuous motion playback or an audio/listening test. The visual observation tools
are read-only and require successful full physical verification earlier in
the same session; a failed sample clears that permission for the source.
The additional read-only `zx7_observe_verified_export_audio` tool serves a
**genuine short 16 kHz mono PCM WAV** as standard MCP `AudioContent` with
its own source-bound hash, requested interval, actual sample count and
basic preview-level signal statistics. It requires the same exact export proof
and denies stale or unapproved sources. The excerpt is at most three seconds;
downmixing/resampling explicitly prevents interpreting it as proof of the
original spatial mix, full-film sync, music quality, dialogue fidelity or
professional mastering. Audio-capable clients may listen to it directly;
clients that ignore MCP audio content will not gain hearing by magic.
Refresh the full-export proof after modifying the file or reconnecting.
For temporal audio inspection, a separately namespaced read-only
`zx7_observe_verified_export_audio_timeline` operation derives bounded 8 kHz
mono peak/RMS time buckets from **actual decoded** authorized native export
bytes already independently verified by SHA256 in the same session. Request
a start time, duration up to five minutes and 2–256 bins; longer projects can
be inspected in separate windows. It observes relative time-bucket signal
energy and silence, not exact original audio PTS, true peak, integrated LUFS,
multichannel spatial sound, speech comprehension or artistic quality. The
read-only operation never returns raw source audio, never accepts arbitrary
host paths or stale export bytes, and has explicit CPU, output and disk budgets.
This is a supplementary diagnostic next to actual bounded WAV listening.

The verifier cannot establish editing originality, artistic acceptance,
source rights or OS process isolation. The import and editing tools retain
their exact upstream schemas; this BODY-owned tool is deliberately namespaced.

To verify the actual standard-client editing route:

```sh
python engines/velorn/mcp-e2e.py \
  --source /absolute/path/to/zx7/third_party/velorn \
  --xvfb-binary /usr/bin/Xvfb --display 127.0.0.1:95
```

The fixture uses the official SDK client and the shipped permission profile. It
checks every advertised schema, rejects outside imports/invalid arguments, edits
and saves two native versions, exports real audiovisual media, disconnects, and
reopens the same revision in a new editor process. It is a scripted integration
fixture, not an autonomous model or artistic evaluation.

## Experimental real-model native editing session

The host-owned [`native-model-client.py`](native-model-client.py) connects an
actual local OpenAI-compatible model to the **real pinned Electron editor**
through the existing official MCP SDK. The *model* decides native operations,
schemas are fetched from the host-granted tool catalog on demand, and each
issued call is journaled **before** submission (no blind write replay).

Example with locally authorized media, a separately running local model and
already created private state/receipt directories:

```sh
python engines/velorn/native-model-client.py \
  --source /absolute/path/to/third_party/velorn \
  --config /absolute/path/to/owner-native-grants.json \
  --state /private/native-editor-state \
  --brief-file /private/owner-brief.txt \
  --receipt /private/new-model-session.jsonl \
  --base-url http://127.0.0.1:8080 --model-id YOUR_ACTUAL_LOCAL_MODEL
```

The app gets **only** the host's explicit grants. Model text is not authority.
The launcher lets the model correct a host policy refusal only when the trusted
BODY bridge proves the editor call was never dispatched. Existing exports stay
protected; BODY never chooses another path or retries the write automatically.
Native errors and lost responses still require state reconciliation. Gateway
budget reservations remain conservative; this is not crash-durable recovery.
The local model must return one `{action,arguments,reason}` JSON decision
per turn; the driver does not bake in a timeline or shot sequence. Actual
MCP text output is supplied to the next decision but only its SHA evidence
is journaled. A real SHA-bound PNG returned by the verified export observer
is supplied as image bytes only if the model supports images.\n\nFor original native WAV, the new optional audio-capable adapter
uses the local OpenAI-style `input_audio` typed content with 16 kHz mono PCM
(3 seconds maximum). Before crossing into a model turn BODY checks the
exact `wav_sha256` and the source export hash reported by the actual
native observer; the local model provider validates the WAV header, length,
sample rate and binary-to-receipt identity. The model server and weights
**must** truly support audio for this to work. Accepted transport and a
model response do **not** prove correct interpretation of music, dialogue,
spatial mix or mastered sound; independent native model trials are still due.
The local model gateway reports **measured monotonic wall time** for each
completed model decision and native MCP call, and includes aggregate timing
in its final response. If the actual local inference server supplies numeric
token counts, they are preserved as `local_server_reported_token_usage`;
otherwise the field is null, **not zero**. These counts are not independently
tokenized, do not include an independently measured VRAM/RAM/power budget, and
must never be presented as verified inference performance or artistic quality.

The receipt is local mode 0600, never overwritten;
after uncertain execution the current project must be reconciled manually
before any deliberate continuation.

**This is a first model-control interface, not a passed live-model evaluation.**
No model weights have yet been independently exercised through this CLI in a
verified creative workload. The current loop is not a durable, cross-restart
creative session and cannot certify edit quality or source rights. A model
calling `finish` does not mean the film is complete or that an expert has
approved it. These are explicit acceptance gaps for [Issue #74](https://github.com/ZX7-Labs/Zx7-creative-studio-/issues/74).
`native-model-client.py` refuses disabling the Chromium sandbox. The upstream
trusted loopback MCP service is still **not** an OS isolation boundary.

## Tamper-resistant source-chain audit for a native model session

A separate read-only audit can inspect the model-issued native operation
journal against the **owner-granted** editor permissions, including the
five additional host-owned verifier/observation names only if the owner
enabled physical export verification. The model cannot grant itself sensors.

```sh
python -m studio_next.native_creative_audit \
  --journal /private/new-model-session.jsonl \
  --host-editor-config /private/owner-native-grants.json \
  --trust-host-pre-dispatch-rejections
```

Use the final flag only for sessions launched through this trusted BODY bridge.
It is independent host authority, not a claim read from the journal. Omit it for
raw native or other plugin sessions; their error metadata cannot prove no write.

For each tool call the driver writes an ordered intent before RPC and a
separate result (or terminal uncertainty), preserving checked result hashes
instead of leaking asset bytes. Host-owned frame/WAV observers cannot be
spoofed by unrelated native tools. Their export digest must be the exact
SHA-256 **already physically verified within the same editing session**.
The standalone audit independently verifies receipt structure, legal call
ordering, complete outcomes, grants, export-to-frame/audio identity and
whether the model elected to revise after observing earlier output. A torn
journal, duplicate records, unknown granted tool, invented media hash, and
a write after an uncertain result all fail.

**Important limitation:** This is an auditable trace and provenance
consistency check, not a cryptographically signed append-only archive.
Neither the auditor nor the driver independently re-decodes media bytes
from the audit journal, proves that a real neural model (rather than a
scripted fixture) issued the commands, proves licensed source rights,
establishes a professional-quality result, or prevents tampering by the
trusted host filesystem owner. Runtime media verification is provided by
the separately tested native export verifier and its physical observers;
a higher-level independent creative/video acceptance remains required.

## Start a local session

For a bounded real-model trial, `scripts/run_native_model_trial.py` downloads
the exact runtime/weight revisions and verifies their sizes and SHA256 values
from [local-model-trial.lock.json](local-model-trial.lock.json). It starts a
CPU Qwen3.5-2B vision model and this existing editor on a normal non-root host.
The script supplies neutral original input footage and a creative brief;
every native editor mutation must come from model inference. Private trial
artifacts retain decisions, supplied image hashes, the source-chain journal,
native projects, exports and runtime logs. This trial deliberately contains
only generated public test inputs; do not publish private client transcripts.

The trial refuses a root/disabled-sandbox editor and has no scripted editing
fallback. Completion requires a model-selected content revision after observing
real pixels, a subsequent save and new verified export, and changed decoded
frame sequences. Token/RAM measurements are not inferred from model size or
invented when absent. A failed or incomplete run remains a failed run; even a
successful technical trial does not certify professional creative quality.
The `ZX7 BODY — Live Local Model Native Editor Trial` workflow preserves its
results, including failures, separately from deterministic renderer tests.
The [measured trial record](../../research/local-model-trial-evidence.json)
retains negative results too. For a local backend supporting JSON Schema
structured decoding, `native-model-client.py --structured-actions` binds only
the control envelope and discovered tool identities. It never supplies an edit
sequence or creative parameter values. Backends without that capability retain
the default interface and strict host-side validation.

Paths must be absolute. Each launch requires a fresh profile; project/staging/output roots can persist. This upstream hardcodes ports 5173 and 19790, so only one instance per network namespace is supported. Occupied ports fail before startup.

```sh
node engines/velorn/cli.mjs \
  --source /absolute/path/to/zx7/third_party/velorn \
  --profile /absolute/path/to/fresh-profile \
  --projects /absolute/path/to/projects \
  --staging /absolute/path/to/staging \
  --outputs /absolute/path/to/outputs
```

For headless Linux install Xvfb, x11-xkb-utils, xkb-data and Electron system libraries, then append `--xvfb-binary /usr/bin/Xvfb --display 127.0.0.1:95`. Choose a free display with no stale lock. The supplied Xvfb uses unauthenticated TCP (`-ac`) for local isolated tests; prefer your own authenticated display in ordinary use. This launcher is not for public hosting.

`--software-gpu` uses Chromium's software compositor. `--no-sandbox` is an explicit exception for disposable restricted root test hosts; it is not the default or an isolation measure.

The process prints a ready record, accepts JSON lines and writes upstream logs to the private profile:

```json
{"id":1,"method":"tools/list"}
{"id":2,"method":"tools/call","params":{"name":"get_project","arguments":{}}}
{"id":3,"method":"tools/call","params":{"name":"create_project","arguments":{"name":"My edit","width":1920,"height":1080,"fps":24,"previewOnly":false}}}
{"id":4,"method":"shutdown"}
```

EOF, shutdown, SIGINT and SIGTERM stop the owned processes; signals also clean up an interrupted startup. Node hosts can import `launchVelorn` from `launcher.mjs`; it accepts an optional AbortSignal and returns `{client,close,revision,rendererUrl,logPath,appProfile,...roots}`. Discovery returns unchanged native schemas plus integration policy annotations. Calls return native MCP content and parsed `.data` for JSON text. Snapshots debounce mutations by 350 ms: `waitForState(predicate)` observes actual upstream state before using fresh IDs.

## Native integration proof

```sh
node engines/velorn/e2e.mjs \
  --source /absolute/path/to/zx7/third_party/velorn \
  --xvfb-binary /usr/bin/Xvfb --display 127.0.0.1:95
```

The fixture creates temporary synthetic media, native video/audio/title tracks, text/keyframes, two preserved project versions, a reopen, a complete application stop/restart with saved-project reopen, and audiovisual export through the existing production Electron export worker. It checks native BODY read/write grants, full original schema preservation, frame/audio decode and SHA256 receipts. This scripted test does not establish autonomous model use, interrupted-render/crash recovery, professional creative quality or complete field coverage. A new receipt is proof only when the command actually succeeds.

## Authority and remaining limits

This is a trusted local transport, not an autonomous-model security boundary. Python BODY must grant individual tools and apply host argument/path policy. Explicit top-level file paths are scoped; network/generation/launcher tools, recent-project lookup, nested plans and batch exports are blocked. Batch targets can nest file paths, so `export_delivery_batch` stays blocked until that structure has a reviewed policy. These checks do not confine the upstream process, remove filesystem races or validate references inside native projects. Open trusted projects only.

The upstream MCP endpoint is unauthenticated loopback at a fixed port; all 130 native tools lack security annotations. Instance identity/token, OS filesystem/network/resource isolation and production completion/progress integration remain release requirements. The application can request Google Fonts and optional services; network-off operation needs egress control or an audited fork patch.

Native split safety: at pinned upstream commit `b3c02adb`, the native
`split_clip` can leave arbitrary effects/keyframes on the left clip rather
than preserving them on the new right clip. BODY's granted Python native
client now **preflights the full target clips** using actual `get_timeline`
and `inspect_clip` read operations. It refuses unknown/enhanced clips and
does not send the destructive split call; clean source clips remain splittable.
Without granted read inspection, a split fails closed. This is explicitly a
**temporary protective measure, not a lossless split implementation**. The
raw upstream loopback MCP port and native GUI can bypass this BODY boundary;
do not treat this as a sandbox or concurrency-safe OS transaction. Lossless
professional effect/keyframe-aware razor behavior, source-clock retiming,
native saves and physical rendered pixels remain pending investigation in
[Issue #72](https://github.com/ZX7-Labs/Zx7-creative-studio-/issues/72).

Native source limitations: audio envelope/EQ and spline-point animation remain partly UI-only; variable video speed does not cover all audio retiming; interchange can lose native styling and rejects editable compounds. MCP checkpoints are memory-only; durable named versions require preserving native files. `export_timeline` has no status tool, so the fixture observes the existing worker log and decodes the output. Use separate title tracks to avoid native overwrite semantics, explicit custom ranges to avoid the default 60-second extent, and `h264_project` for project/custom dimensions. Graphics-only MCP exports are rejected by an older readiness check.
