# Framework-independent backend process contract

Implemented in app/api/backend.py using existing Pydantic dependencies.
BackendService is an in-process dispatcher around ProjectWorkspaceService.
It opens no ports and starts no transport or background worker.

## Request

BackendRequest fields:
- request_id: nonempty string; generated UUID if omitted
- method: allowlisted workspace method name
- params: JSON object of method parameters
- unknown top-level fields are rejected

Starting an action:

~~~json
{
  "request_id": "agent-001",
  "method": "request_agent_execution",
  "params": {"prompt": "Create feature.py"}
}
~~~

The envelope request ID becomes the agent request ID. A conflicting params.request_id
is rejected. Continuation commands have separate command IDs and target the original
agent request in params:

~~~json
{
  "request_id": "approval-command-001",
  "method": "approve_agent_action",
  "params": {"request_id": "agent-001", "tool_call_id": "retained-call-id"}
}
~~~

Resume is a separate command using resume_agent_execution with the same target IDs.
Neither operation accepts replacement tool arguments.

## Response and errors

BackendResponse fields:
- request_id: this command's ID
- success: whether the operation was handled successfully
- action_state: running, permission_required, approved, completed, failed, denied,
  cancelled; null for boundary errors
- data: method-specific JSON (AgentResponse for agent operations)
- error: null or ErrorResponse {success: false, code, message, details}
- events: recorded AgentEvent objects for an agent response

Agent failure is a handled operation with success=true and nested status=failure.
Dispatch/validation failure has success=false and an error envelope.
The outer success flag is never a verification result.

Serialize with model_dump(mode="json") / model_dump_json(). Invalid envelopes
without a usable ID return request_id="invalid". Raw exceptions/stack traces stay
in backend logs, not response envelopes.

## Progress/event model

AgentEvent contains request_id (agent ID), increasing sequence, event_type,
current_state, optional tool_call_id, and timestamp. Recorded event types:
state_changed, tool_started, tool_finished, permission_required,
permission_approved, recovery_finished.

get_agent_events(request_id, after_sequence=0) returns events after a cursor.
Action responses include event history. These are recorded synchronous observations,
not live streaming. Dispatch holds a lock during a command and cannot simultaneously
service polling. A future transport/worker may extend delivery without inventing
state transitions or bypassing the service.

The workspace timeline is separate domain history assembled by IntelligenceService.

## Idempotency and lifetime

Within one BackendService instance an identical command ID/input replays its
original response. Different input under that ID produces action_conflict.
Use a fresh command ID to fetch the latest state. The orchestrator separately
retains each agent request's latest response.

Command caches, pending actions, and events are not durable across restart.
There is no cross-crash exactly-once guarantee.

BackendService serializes workspace commands using RLock. Direct workspace callers
must serialize access themselves. The orchestrator also serializes its lifecycle.
Only one request can await approval per orchestrator.

The host owns process creation, LLM configuration, explicit tool registration, and
matching workspace/agent roots. Client parameters cannot select arbitrary Python
attributes or change the root behind an existing workspace. Dispatch uses an
explicit allowlist.

## Shutdown

Send shutdown as a normal command. It runs after the current synchronous call,
cancels pending workspace requests, revokes pending approvals, closes the facade,
and returns {closed: true}. New commands fail with service_closed.

Identical commands, including shutdown, can replay cached acknowledgements without
executing more work. Shutdown does not roll back completed side effects or interrupt
in-flight subprocesses. Existing SQLite connections are short-lived and closed by
the store. A future host should await acknowledgement before normal termination.
Forced process termination has no cleanup guarantee.

## Scope

No HTTP/WebSocket/stdio transport, Electron/Tauri integration, package installation,
or OS sandbox is implemented. See [INTEGRATION_HANDOVER.md](INTEGRATION_HANDOVER.md)
for service methods, verification outcomes, permissions, errors, and limitations.
