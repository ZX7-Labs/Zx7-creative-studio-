# ZX7 — Universal Execution Architecture / Decision Record 01

Status: architecture decision and executable first increment, NOT a claim that the whole product or autonomous film is complete.

## Product boundary

ZX7 is an extensible creative BODY operated by replaceable Brains. Video is the first demanding physical acceptance workload, not the architecture boundary. Future audio, graphics, 3D, design, document and other real applications must be admitted using the same trusted host contracts.

| Layer | Existing ZX7 owner | Actual authority |
|---|---|---|
| Intent, artistic judgment, tool selection | Replaceable Brain / native creative controller | Creative choices only |
| Live tool enumeration and typed ABI | studio_next/capability_fabric.py | Installed source schemas |
| Grants, prerequisite checking, locked dispatch | studio_next/capability_gateway.py | Trusted host |
| Native object identity | Optional engine-owned read-only reference adapters | Real installed object IDs |
| Write intent and crash recovery | studio_next/capability_attempts.py | Durable host SQLite |
| Invocation ceiling | studio_next/capability_session_budget.py (this increment) | Host-only process/session quota |
| Creative mutations and observations | Actual installed editors/renderers/other adapters | Native software |
| Delivery acceptance | Independent source, physical and artistic verifiers | Evidence, not model claims |

## Execution contract

1. Host connects installed tool sources and registers explicit grants; the Brain cannot invent capabilities or give itself permissions.
2. Brain searches the live catalog, describes the selected operation's real input schema and chooses parameters.
3. Host rechecks current tool identity, permission, schema and machine prerequisites under the engine lock.
4. When a native object policy is available, host independently reads the current IDs and validates each explicit reference.
5. Optional host-owned session budget atomically reserves one global call slot, and a write slot for a mutation, BEFORE durable admission and any native RPC.
6. Durable host journal records the request identity BEFORE non-idempotent writes; uncertain results must be reconciled, not automatically replayed.
7. Native software performs the work. Observers then establish actual machine state and output; independent quality review makes any artistic acceptance claim.

External engine state may change between observation and call. This does NOT provide cross-app atomic transactions. Each adapter remains responsible for authorization, local concurrency and after-write observation.

## Shared creative project, without a universal-format trap

The October 29 repository review identified a distinct blocker: the
legacy film IR requires nonempty shots. An audio-only project, layered
poster or editable 3D scene must NOT need fake film shots just to enter
ZX7. The reusable *control layer* should describe owners, source IDs,
dependencies, versions, time/color/audio meaning, native subproject
references, permissions and evidence. Real scene graphs, audio DAW
sessions, video timelines and design layers must stay in their proven
native formats; interchange explicitly reports unsupported or lossy
transformations. Migrate consumers gradually behind adapters instead
of breaking existing film execution, graph leases and saved projects.

The execution gateway remains domain-neutral even for future noncreative
software. The shared project envelope is a separate optional creative
product concern, not a requirement that every app become a film project.
No rewrite or migration is authorized merely by this decision note.

## Four levels of evidence

A — Discoverable: exact installed/granted operation exists.
B — Admissible: input contract, live grants, references, prerequisites and budget permit a call.
C — Physically effective: actual native app readback, saved/reopened project or independently decoded produced media.
D — Accepted: delivered output satisfies original rights/source policy and independent artistic/product acceptance.

A and B are NOT proof of C; playable/exported C is NOT proof of D. Tests using artificial engines prove only host-side admission mechanics.

## First source-neutral budget: present scope and limits

A host may explicitly instantiate CapabilitySessionBudget(max_calls=N, max_writes=M, per_source={...}) and pass it to CapabilityGateway(session_budget=...). It has NO default hidden limits and preserves behavior of existing unbudgeted callers.

A single atomic counter spans engines connected through the same budgeted CapabilityGateway and concurrent invocations. Direct legacy runners outside that gateway remain unbudgeted; routing them is a separate integration task. Optional per-source limits restrict hot spots. Invalid model parameters do not consume a slot. Reservations conservatively remain consumed if a later durable duplicate check fails, the app reports an error, the process crashes or the native result is uncertain. The host receives an aggregate budget receipt containing no original inputs or media.

Critical scope: this is an IN-PROCESS ADMISSION LIMIT on the configured gateway, NOT a token usage meter, dollar budget, production success metric, blanket guard for every legacy call path or durable 24-hour spending control. Process restart can instantiate a fresh budget. Real autonomous agents require durable cross-process accounting that includes model usage and real external provider costs before claiming cost control.

## Work sequence by risk removed

1. Prove cross-source budgets and no-dispatch on exhaustion using video, motion, graphics, documents and concurrent independent sources. Kill if any native call can pass an exhausted host budget; preserve prior editor workflows.
2. Repeat real Qwen → actual original camera → genuine native edit with privacy-safe categorization of the exact model-created command and the editor outcome. Kill or change Brain/observation strategy if the model still cannot choose a valid command with live ABI.
3. Prove an independently installed non-video adapter reaches physical machine effect with the SAME host boundary; a 2D typography/motion brief with Hindi text and a targeted revision is the initial comparison. Kill if the gateway needs artistic presets or video operation names.
4. Add a durable, cross-process model/tool/provider budget and consent gate only after there is physically demonstrated product value. Kill if accounting cannot be reconciled to measured source usage or external invoice.
5. Compare delivered films/designs independently against practical creative brief; never use passing infrastructure tests as an artistic grade.

## Choices rejected

- Rewriting every native creative engine: costly duplication and long-term maintenance.
- One enormous do-everything model prompt: does not enforce real grants, idempotency or resource ceilings.
- One fixed giant Brain for every action: no evidence-based model choice and unnecessary expense.
- Thousands of tool schemas supplied on every turn: bloats context and creates ambiguity. Scoped live search and describe retain actual affordances.
- Treating MCP success as completed project: confuses protocol, native edit, persistence and artistic quality.

## Borrowed standards (not invented technology)

MCP tools (https://modelcontextprotocol.io/specification/2025-11-25/server/tools) supplies tool discovery/call and explicit errors. OpenTelemetry GenAI conventions (https://opentelemetry.io/docs/specs/semconv/gen-ai/) distinguish inference/tool spans and require honest usage measurement. Durable intent/outbox concepts inform conservative write-recovery semantics.

## Six-month pre-mortem

Likely failure: hundreds of impressive partial branches but no verified full user deliverable; uncontrolled agent invocation/cost loops; accidental non-idempotent write replay; dependence on an unmaintainable editor/format; and confusing tests with output quality. Countermeasures: narrow hypothesis-driven experiments, host execution quotas, exact-head CI, source/license custody, independently observed artifacts, and regular end-to-end user acceptance.

Progress rule: always distinguish *committed source*, *CI passing*, *real native effect*, *independent acceptance* and *unknown*.
