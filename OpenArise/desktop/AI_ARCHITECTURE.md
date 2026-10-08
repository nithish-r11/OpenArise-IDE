# AI workspace architecture (October 6 Ollama and recovery acceptance)

## Existing backend, desktop transport

The integration path is:

```text
AIPanel / useAI
  → BackendClient
  → window.openarise.request (preload)
  → trusted main-window/frame/page and current-project checks
  → DesktopBackendService / WorkspaceBackendAdapter
  → fixed Python interpreter, desktop/python/agent_host.py, bounded JSONL
  → existing BackendService.dispatch
  → existing ProjectWorkspaceService
  → existing AgentOrchestrator, PermissionManager and CompletionGate
```

No second agent, model client, HTTP API, permission system, test engine or recovery
engine was created. Production configures the existing OllamaProvider using the
existing backend settings (OLLAMA_HOST/OLLAMA_MODEL/OLLAMA_TIMEOUT_SECONDS), with DesktopSettings defaults 127.0.0.1:11434/qwen2.5-coder:7b/180 seconds. Environment and backend .env values override them; standalone Settings defaults remain compatible.
The host starts with the fixed backend directory as cwd so the backend's existing
.env configuration lookup is preserved. Credentials/configuration are never sent
to React. No model pulls, package installs, provider configuration UI or Luminous
inference are included.

The interpreter is the existing ai-engine/.venv Python. The host explicitly
registers the existing read_file, write_file, execute_python and execute_tests
tools with production PermissionManager(test_mode=False). Person 1 controls tool
execution and verification. AI tool execution uses that backend interpreter;
the separately displayed Phase 3 project interpreter applies to manual Run/Test.
Opening a project loads bounded context without starting inference. Context loading, refresh or submission lazily
starts the workspace host; an available host does not imply that Ollama/model
inference is available.

## Requests, context and lifecycle

AIRequest contains requestId, prompt, optional context and optional projectRef.
The UI sends the prompt and selected project reference, not file contents.
Electron validates the reference against the native-picker ProjectService root.
The root/executable cannot be overridden by renderer data. AI history has at most
20 request entries in React memory, scoped to the selected project; it is lost on
reload/exit and never written to localStorage or a database. Draft text is retained
on unavailable/failed submission and original prompts remain in history. Reuse
prompt restores a history item into the composer.

Submission locks immediately, before awaiting transport. Duplicate Enter/click
submissions are rejected while active, and a retained permission action prevents
starting another request. Dirty editor state blocks submission and resume in the
UI and main process; an AI write can still race later edits, so Phase 2 disk revision
conflicts remain authoritative. Reopen clean tabs to inspect files changed by AI.
Project replacement is blocked while AI work or a permission action is active.

Before initial execution, the host calls the existing refresh_workspace method. Project opening performs the existing initial scan; context loading/refresh reads the snapshot and environment without initializing agent memory. ProjectWorkspaceService automatically incorporates the
existing ProjectIntelligenceContextAdapter's bounded summary. The desktop context
view uses that same adapter and shows only factual counts and environment
observations. Unknown context is labelled unavailable/not loaded, not invented.

The original envelope request ID is preserved as the agent ID. Approval, resume,
denial, cancellation and retrieval each use a fresh command ID and target the
original agent/tool IDs. BackendService retains its existing idempotency cache;
the desktop does not replace it. Cross-crash exactly-once execution is not claimed.

## Permissions

A permission card begins with pending_action returned by the backend. Its final decision is retained in session history.
It shows risk category, safe tool name, safe relative resource if available and
request/tool IDs. Raw command arguments, file content and replacement arguments
are never exposed or accepted.

Allow sends approve_agent_action and, only after a confirmed approved response,
sends a separate resume_agent_execution with the same retained IDs. Approved work
can be resumed separately if needed. Deny and Cancel call the existing backend
methods. No action is executed in React. No local grant table or automatic
PermissionManager approvals were added. Partial work is not rolled back.

A transport error retains the last known pending card and enables Refresh request
result. Re-query the original request before retrying actions. If the host is lost,
inspect disk for partial effects; restart the desktop before submitting new work.
A pending-state transport loss conservatively prevents project switching rather
than assuming the outstanding action was safely cancelled.

## Results and recorded activity

Outer response.success indicates handled dispatch only. Nested agent status
distinguishes success, unverified, failure, permission_required, approved, denied
and cancelled. The UI displays Verified by CompletionGate only when nested status
is success, the action/lifecycle are completed and verification.overall_status is VERIFIED, with consistent coverage and no returned failure, active stale evidence or unresolved issue. It never
converts unverified to success.

While waiting, Submitting and Backend command active describe local transport
state. No inferred Thinking/Planning/progress percentages are shown. Backend
states and events appear only after the synchronous command returns. Event lists
explicitly say recorded observations, not live streaming. No polling claims live
access while BackendService holds its synchronous lock.

Tool presentation includes allowlisted tool name, ID, executed/success state,
exit code and timestamp. The projection excludes tool arguments/output, source
content, arbitrary LLM action prose, evidence payloads, raw exceptions and stack
traces. The final lifecycle message, numeric CompletionGate report, safe requirement results and bounded evidence summaries/flags are shown.
Text-only action messages are now displayed as redacted inert proposal text (maximum 8,000 characters); HTML/Markdown is never executed. Tool-action prose remains withheld.

Recovery states/events and counts appear only when returned. The existing backend
now retains its real diagnosis and RecoveryResult in AgentResponse. Its retained
recovery plan pauses for each exact write/execute approval and the mandatory pytest
retest through the same approve/resume commands. No new IPC or recovery engine is
introduced. Unknown tools and dependency installation remain blocked.

The existing verifier preserves failed evidence. Only an actual RECOVERED result
with linked, executed, passing retest proof for the same requirement can resolve
that historical failure. Fresh source/test/config fingerprints must match the
current project. Writes invalidate old test proof; a later passing retest may
supersede stale passing proof, never silently erase a failure. Refreshing a retained
request reevaluates changed execution proof with the same CompletionGate.

Backend pytest uses a fresh bytecode namespace so rapid same-size rewrites cannot
reuse a timestamp-valid old .pyc. Recovery memory stores the actual returned plan.
Planning receives failure facts and diagnosis, excluding completed request steps
that could accidentally repeat an intentional fault.

Projection exposes only safe resolution IDs, failure/recovery summaries and
recorded RETESTING state. Tool arguments, outputs and fingerprint payloads remain
withheld. Recovery-finished activity can use the last returned outcome only for
the matching latest cycle by its recorded timestamp; earlier attempts keep outcome
not supplied. Activity remains synchronous returned history, never live streaming.

## Presentation safety and bounds

The existing dispatch/lifecycle contract is retained. AgentMessageAction extends AgentAction with literal message type and zero permitted tool calls for answer-only requests. agent_projection.py is a
desktop-only allowlisted presentation projection of method data inside the existing
response envelope. Context uses intelligence_summary from the existing adapter.
Safe pending cards omit tool_call.arguments; tool results omit output/error. The
typed desktop view schema documents this subset rather than pretending to expose
the full raw BackendService payload.

IPC validates exact operation shapes, project references and IDs. Requests are
limited to 65,536 JSON code units; the composer limits prompts to 12,000 characters.
Stdio responses are capped at 512 Ki code units and validated against correlated
command IDs, enum values, safe field sets, monotonically increasing event sequences
and bounded arrays. At most the latest 200 recorded events and 100 tool results
are presented. Phase 7 additionally bounds evidence to 40 records, requirements/results to 30, evidence reference lists to 20 and missing/remaining issue lists to 10. Partial collections are labelled. SecretRedactor is reused for bounded text/path fields; raw payloads
are omitted entirely. Identifiers are bounded. Rendering uses React text nodes,
without HTML/Markdown execution or interpreted shell output.

Main labels injected test-adapter responses as test_fixture; the renderer cannot select that adapter. Phase 7 AI/activity views visibly distinguish fixture, backend and unreported sources. No fixture proves live Ollama behavior.

The preload still exposes no Node, filesystem, child_process, raw invoke or generic
shell. Electron sandbox, context isolation, web security, navigation restrictions
and CSP are unchanged. The existing main-process ownership and before-quit path
await work, BackendService shutdown acknowledgement and file-host cleanup.

## Cancellation, shutdown and process limits

Pending actions can be cancelled. A synchronous in-flight request cannot be
reliably interrupted through this contract, so no active-request Cancel button
claims otherwise. Shutdown waits for it and then sends the existing shutdown
command, which cancels retained pending work and revokes approvals. There is no
second shutdown protocol or rollback promise.

The AI host reuses Phase 3 Windows Job Object ownership before initializing the
backend; POSIX uses a process group. Invalid transport output/lost connections
fail closed and remove the owned process tree where supported, but executed side
effects may remain. This is not an OS filesystem/network sandbox. Project Python,
backend tools and configured providers run with user privileges. Adversarial POSIX
processes can detach. Forced process loss and main crashes have no cleanup or
exactly-once guarantee.

## Offline testing

UI tests use typed recorded fixtures. Python integration tests instantiate the
real BackendService/ProjectWorkspaceService/AgentOrchestrator with an offline
LLMProvider, then exercise real permission gating, write execution, denial,
cancellation and CompletionGate's unverified outcome in temporary projects.
A process integration test starts the production stdio host and reads context/
environment and shutdown without requesting inference.

Electron smokes inject a BackendProcessAdapter through the Node entry-point
composition function. This test seam is not exposed to React or controlled by a
production environment variable/command-line mock flag. They enter a prompt and
exercise the real secure IPC, permission card, approve/resume and unverified
result. The default unit/host/smoke suites do not require real Ollama.
The separate source live-acceptance helpers require the actual installed model,
invoke real backend handlers and never inject AI results.

## Answer-only request and provider failure handling

The actual AppShell defaults to Answer only. context_data.response_mode=text_only
travels through the same allowlisted request_agent_execution envelope, and the
existing bounded adapter adds factual context. AgentOrchestrator still owns context,
requirements, lifecycle and CompletionGate; it uses AgentMessageAction and the same
OllamaProvider.generate_structured with a JSON schema in Ollama's format field.
The message includes the requested answer rather than a next-tool plan. Invalid
tool output fails before any execution. Agent actions mode retains the existing
AgentAction/tool/permission path. No renderer HTTP call or second implementation
exists. [Ollama generate API](https://docs.ollama.com/api/generate) documents schema
format and non-streaming responses.

The provider checks the exact configured model tag before generating. Wrong-size
tags cannot count as installed. Stable provider reasons distinguish unavailable,
model unavailable, timeout and generation failure; AgentOrchestrator maps these
to existing failure categories, retains its safe failure contract and evaluates
CompletionGate on failures. Projection retains safe outer command failure reasons.
The host formatter keeps developer stack frames and exception types but omits
exception values; main's stderr budget is 16 Ki characters with secret/URL/control
redaction. Stdio stdout remains reserved for the existing correlated JSONL envelope.

Generation defaults to a 180-second read timeout (30–900 configurable), startup/
read IPC to 30 seconds and execution/resume transport to 15 minutes. No active
inference cancellation or automatic retry is claimed. Live source UI evidence and
the live recovery results and remaining UI/package checks are in
OLLAMA_INTEGRATION_REPORT.md and ../FINAL_ACCEPTANCE_REPORT.md.