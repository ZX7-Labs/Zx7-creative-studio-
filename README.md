# ZX7 BODY

An open-source creative execution system operated by AI. The goal is one
workspace for design, editing, animation, CGI, VFX and sound, with detailed
control over the creative project and its output.

The current implementation provides a tool catalog, editable project controls,
native Blender projects, media rendering, source custody and resumable jobs.
Available operations depend on the engines installed on the host. Development
is active; this is not a completed all-purpose creative suite.

The current [architecture](docs/architecture.md),
[reuse research](docs/reuse-research.md) and
[video research plan](docs/video-research-plan.md) record foundation decisions,
their evidence and remaining acceptance gates.

## Native video editor

The complete [Velorn editor](third_party/velorn) is pinned at
`b3c02adbd5c0779feb8abf34978299e9502cc0e7`. Its native project, UI,
compositor, mixer and exporter are reused. Run `git submodule update --init
--recursive` to obtain source; [setup and native export test](engines/velorn/README.md)
explain how to run it locally without a hosted AI API.

The [execution record](research/editor-integration-evidence.json) verifies a
scripted native edit, saved revisions, application restart/reopen and actual
audiovisual export; it is not an autonomous AI or artistic-quality evaluation.

Python `LocalEditorClient` preserves native MCP schemas and requires explicit
host grants. `body_catalog(workspace, editor_client=client)` attaches granted
operations to the existing BODY catalog. Professional field completion,
autonomous creative acceptance and complete desktop distribution remain open.

For an MCP-capable local AI client, the [standard MCP launcher](engines/velorn/README.md#connect-a-local-ai-client-through-standard-mcp)
starts the existing editor and the permissioned bridge in one process. Install
the optional `.[editor]` extra; host configuration controls grants and media
roots. Models remain separate and no hosted AI API is required.
The [SDK-client execution record](research/editor-mcp-evidence.json) preserves
the measured scope and exact tested source digests.

## Create and revise a native project

On Linux, install Python 3.11+, Node, FFmpeg/FFprobe and the pinned editor's
[build dependencies](engines/velorn/README.md). Run Electron as an ordinary user
with its Chromium sandbox enabled. Start a local OpenAI-compatible model server
separately. Studio selects it automatically if `/v1/models` lists one
model. If the server lists several, pass `--model-id` to choose one.

```sh
python -m pip install '.[editor,production]'
zx7-studio init ./my-studio --source ./third_party/velorn
zx7-studio doctor ./my-studio
zx7-studio run ./my-studio --brief-file ./brief.txt --asset ./source.mov --rights 'I own this footage'
zx7-studio status ./my-studio
```

The `--source` override is optional when a built editor is already present at
`share/zx7-studio/velorn` under the active Python installation or in the
matching source checkout.

`doctor` checks installed runtime files, the source pin, editor build and actual
local model inventory before inference. Sessions discover the granted native
capabilities in bounded groups to fit the current tool request. It reports
missing setup; it does not
install an engine or download model weights. A graphical display is required;
for headless runs supply `--xvfb-binary /path/to/Xvfb` if available.

Revise an existing saved native project using the same command with
`--project ./my-studio/projects/PROJECT_DIRECTORY` and a new brief. Before opening
the project for editing, the host keeps a private copy of its exact saved native
document in the run's session directory. The status records the checkpoint path,
byte count and SHA-256. The copy references the existing project media and stays
available after an interrupted revision. The host opens and verifies the selected
project before the model chooses editing actions. Each run preserves
private source copies, rights declarations, a native journal and status under
its workspace. A completed run means the model finished with verified export
evidence; artistic approval remains separate. An interrupted or failed run is
retained for inspection and is never automatically replayed.

Use `run --reviewed-revision` to require two separately verified native renders
of the same timeline, with a model-observed frame on each side of an
acknowledged content edit. The second render must follow the latest edit and
its verified bytes must differ. The NVIDIA route also requires explicit
`--allow-cloud-image-upload` for this profile. Production quality assessment
still requires reviewing the actual picture, motion and sound.

`status` also checks the owning runner's live kernel locks. A saved `running`
record whose runner has died is annotated as needing attention without rewriting
that record or claiming recovery of an editor/render process.
For a running session with a private native journal, `native_progress` reports
acknowledged editor writes, recorded export verifications, and the latest
journal event, including a submitted native tool still awaiting a recorded
result. It reads complete records only and leaves the journal intact. Export
counts summarize earlier verifications rather than inspecting current media.

For the supported hosted NVIDIA adapter, choose `--provider nvidia` at `init`
and provide `NVIDIA_API_KEY` only to the trusted runner environment. Studio
uses the adapter’s default model unless you supply `--model-id`. Both
providers use the same native session and host grants. Uploading observation
images to NVIDIA additionally requires `--allow-cloud-image-upload` on `run`;
source text and tool results are part of the hosted model conversation.

Add `--allow-public-research` to `zx7-studio run` when the project can send
model-written public queries to external research services. Either model
transport can choose image, footage, sound or scholarly lookups, or search
English and Hindi Wikipedia for creative references. The built-in sources
require no separate search service or API key. For broader web coverage,
an owner can supply a local SearXNG instance with JSON output enabled via
`--searxng-url http://127.0.0.1:8082`. Studio keeps
these tools off by default and gives an enabled run eight research calls.
The model can repeat details from its brief in a query. Enable this flag only
when those details can be disclosed to the configured research services.
Search results are untrusted leads. Import or reuse of media requires separate
rights and source checks. See the [SearXNG search API](https://docs.searxng.org/dev/search_api.html).

The wheel contains MIT-licensed BODY code and a GPL-3.0-only native runtime.
It ships both license texts and upstream notices; its distribution metadata
records both licenses. The root MIT license does not replace the native
runtime's GPL terms. See the [native source and notices](engines/velorn/README.md).

The installed package includes the MCP bridge; the complete pinned editor,
its Node dependencies and model runtime are installed separately. The existing
BODY service and specialized engine tools remain available below.

## Run locally

Python 3.11+ is required. The service is tested on Linux. Install FFmpeg/FFprobe
for media operations, Blender 4.5+ for native motion projects, and Inkscape for
SVG rasterization. These applications are installed separately.

```sh
python -m pip install '.[production]'
zx7-tools --workspace ./workspace
export ZX7_BODY_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
zx7-body --workspace-root ./workspace
```

Keep the same token in a second terminal to inspect the running service:

```sh
zx7-client tools
zx7-client describe body.motion_project
```

The authenticated service listens on `127.0.0.1:8765`. Discover tools and their
document schemas before submitting a project. Native operations run on the host;
missing engines are reported as requiring setup. Optional EXR and tracking
dependencies are available through `.[vfx_exr,vfx_tracking]`.

After a verified archive is restored with relocation enabled, use
`zx7-relink-mlt --workspace NEW --old-workspace OLD --source NEW/edit.mlt --out NEW/relinked.mlt`
to create a separately verified native project at the new media locations.
The old edit and prior execution history remain preserved; renders run again.

## Project and checks

- [AGENTS.md](AGENTS.md): product intent and development direction.
- [CAPABILITIES.md](CAPABILITIES.md): full original A–L capability scope, engineering invariants and release gates.
- [ENGINEERING_STANDARD.md](ENGINEERING_STANDARD.md): independent engineering judgment, research and verification; show original work when transitioning from a capability considered complete.
- `studio_next/`: execution, project controls, service, clients and tests.
- `motion_studio/`: existing 2D compositor and sample projects.
- `creative_director/`, `director_research/`, `voice_lab/`: optional research tools.
- `.github/workflows/`: automated verification and optional manual experiments.

GitHub Actions runs native rendering, source checks, security, browser, custody
and interchange tests. Run focused tests with `python -m unittest`; native tests
require their corresponding host engines and Python dependencies.

## Licenses

Repository code is covered by [LICENSE](LICENSE), except files with their own
notices. Velorn and the integration launcher are GPL-3.0-only; root terms do
not relicense them. External applications, model
weights, fonts, voices and media have their own terms. Research scripts do not
grant commercial rights to their models; the F5/XTTS comparison uses models with
non-commercial restrictions. Review the selected engine and asset licenses for
your deployment.
