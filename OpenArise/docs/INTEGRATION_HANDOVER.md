# Backend integration handover for Person 3

This is the current implemented contract after backend hardening. It supersedes
the earlier Phase 6 handover and historical Person 1 approval assumptions.
The backend remains Python/Pydantic with the existing managers and agent engine.
No framework, dependency, desktop shell, or transport server was added.

## Entry points and ownership

Use app.api.services.ProjectWorkspaceService(project_root, orchestrator=None).
Person 3 must not construct scanners, health engines, drift detectors, or another
graph/context/requirement subsystem. The service shares the mapper's graph manager
and uses the existing RequirementManager, BlueprintManager, EnvironmentManager,
and IntelligenceService. Agent requirements retain their original IDs.

For a future process wrapper use app.api.backend.BackendService(workspace).
It serializes commands, validates envelopes, dispatches an explicit allowlist,
and returns typed response/error/event objects. It is an in-process boundary.
See [BACKEND_PROCESS_CONTRACT.md](BACKEND_PROCESS_CONTRACT.md).

Inject an AgentOrchestrator with the same resolved project root and explicitly
registered tools. Use PermissionManager(test_mode=False) in production.
Observation-only workspaces need no agent or LLM connection.

## Available service methods

Methods return SuccessResponse(data=...) or raise ApiError. Data is a JSON-compatible
snapshot, not a live manager object.

| Method | Parameters | Result/behavior |
| --- | --- | --- |
| get_project_information | none | Project identity and root |
| get_project_state | none | Cached file/module/dependency observations |
| get_blueprint | none | Initial scaffold, tracked requirements, configured features/tasks |
| get_requirements | none | Tracked requirements and verification status |
| get_traceability_graph | none | Production graph including inferred-link flags |
| get_environment_status | none | Cached interpreter/venv/Git observations |
| get_health_report | none | Environment, dependency findings, health checks |
| get_intelligence_snapshot | none | Project/blueprint/graph/health/requirement summaries, timeline, cached drift |
| get_timeline | none | In-memory workspace events |
| refresh_workspace | none | Rescan, remap, reevaluate health, invalidate cached drift |
| create_requirement_baseline | requirement_id | Capture related IDs and per-implementation hashes |
| get_drift_report | baseline_dict | Compare cached observations, cache finding, record timeline event |
| request_agent_execution | prompt, context_data=None, request_id=None | Start/retrieve an agent request |
| get_agent_execution | request_id | Last response for that agent request |
| get_evidence | request_id | Actual evidence records for that request |
| get_agent_events | request_id, after_sequence=0 | Recorded events after a sequence cursor |
| approve_agent_action | request_id, tool_call_id | Record permission without executing |
| resume_agent_execution | request_id, tool_call_id | Recheck permission; execute stored work |
| deny_agent_action | request_id, tool_call_id | Deny pending work; terminate remaining calls |
| cancel_agent_execution | request_id | Cancel pending work; revoke its approval |
| shutdown | none | Cancel pending workspace work and close the facade |

## Read operations versus actions

Observation never executes project code, installs packages, or writes project files.
Construction/refresh updates in-memory caches. Refresh and drift evaluation can add
timeline events: read-only means no filesystem mutation or project execution,
not immutable Python objects.

Agent actions can write/execute through registered tools and PermissionManager.
Constructing an orchestrator initializes project-local SQLite memory/checkpoint
directories under .openarise. An observation-only workspace creates no such files.

Requirements, blueprints, graph, timeline, action responses, and pending actions
are in memory. There is no watcher; call refresh_workspace after external changes.
Initial blueprint generation does not invent features/tasks or semantic mappings.
Agent requirements are adopted automatically. Feature/task authoring still uses
the existing backend managers; no desktop authoring API is added in this phase.

## Agent lifecycle and permission continuation

AgentRequest contains request_id, prompt, and optional context_data.

1. Retain the request and extract conservative requirements from the user's text.
2. Build the existing ContextManager summary with bounded project intelligence.
3. Generate one AgentAction and retain a deep copy.
4. Execute its registered tools in order; collect results and associated evidence.
5. Stop at the first ASK tool, retaining the exact call and remaining action.
6. Approve explicitly, then resume the retained action without another LLM
   action-generation call. PermissionManager is checked again before execution.
7. Evaluate drift and CompletionGate before normal terminal responses.

A permission-required response includes:
- status/action_state = permission_required
- current_state = PERMISSION_REQUIRED
- pending_action = {request_id, tool_call_id, tool_call, risk_level,
  action_index, approved}
- earlier tool results, requirements, and events in data
- verification = null while the action is pending

Approval returns status/action_state = approved and does not execute. Resume
accepts IDs only, never replacement arguments. Revoked approval leaves work pending.
DENY policy overrides stored approval. Changing a registered pending tool or its
risk invalidates continuation; cancellation remains possible.

Only one request can be pending per orchestrator. New work cannot replace it.
Unknown IDs, mismatched call IDs, and resuming terminal work are lifecycle errors.
An identical request ID/input retrieves the latest response without reexecution;
different input with that ID is a conflict. Completed prefixes are not replayed.
Approvals are revoked after use, denial, or cancellation.

Deny/cancel terminates the remainder without undoing earlier tools. Cancellation
currently applies to retained pending work, not in-flight synchronous LLM calls or
subprocesses. Pending actions and idempotency are not durable across process crashes.

Recovery retains the existing planner/engine/checkpoint/policy architecture.
Every actual recovery tool and validation command needs permission; plan-level
approval is insufficient. Automatic dependency installation is disabled.
Blocked recovery plans do not yet share the primary action's resume workflow.

## AgentResponse and verification semantics

AgentResponse includes request_id, current_state, action_state, status, message,
pending_action, and data. Data contains action_type, agent_message, tool_calls,
tool_results, requirements, evidence, verification, and events.

| status | Meaning |
| --- | --- |
| permission_required | Exact action retained; awaiting permission |
| approved | Permission recorded; awaiting explicit resume |
| success | Normal execution finished and CompletionGate returned VERIFIED |
| unverified | Execution finished but not every requirement was verified |
| failure | Tool or agent processing failed; inspect retained results |
| denied | Pending action denied; remainder not executed |
| cancelled | Pending action cancelled; earlier side effects remain |

SuccessResponse.success and BackendResponse.success mean the service operation
was handled. They do not establish task success. Inspect the nested agent status.

Requirement extraction retains prose as one requirement and explicit multiline
list items separately. It does not claim semantic decomposition or invent
acceptance criteria. IDs/descriptions are included in the generation prompt.
ToolCall.requirement_ids associates evidence; a single requirement is the default
association. Unspecified associations in a multi-requirement request create no
attributed evidence. Unknown IDs prevent that tool call from executing.

Successful writes/reads supply supporting evidence. Actual TestExecutionTool
results with exit code zero supply direct TEST_PASS evidence. A name containing
"test" cannot manufacture proof. Failed executions are contradictory, and negative
facts override claimed direct strength. File/symbol evidence is checked against
files/AST; stale or invalid references block verification. Later mutation-capable tools invalidate prior passing test evidence; a fresh passing test can supersede stale passing evidence, but never contradictory evidence.

Legacy manually constructed TEST_PASS evidence remains a trusted backend input.
The facade provides no arbitrary evidence-submission API. Passing associated tests
does not prove general semantic correctness of arbitrary user requests.

CompletionGate is the final verification authority. NOT_VERIFIED dominates
INCONCLUSIVE, then PARTIALLY_VERIFIED, then VERIFIED, independent of requirement
order. Empty requirements are INCONCLUSIVE. Report.tests_executed counts distinct
test tool invocations, not individual pytest cases. Recovery attempts are counted,
but recovery claims never erase failed evidence or manufacture task verification.

## Intelligence, traceability, and timeline

ProjectIntelligenceContextAdapter and ContextManager share an allowlist:
project_name (redacted, 120 input characters maximum), total_files,
requirements_count, traceability_nodes, health_issues, missing_dependencies.
Counts must be bounded nonnegative integers. Unknown fields, source contents, and
arbitrary nested objects are excluded. The facade's factual summary overrides a
caller-supplied intelligence_summary. Recent tool summaries exclude raw output.
This summary is included in the actual LLM generation prompt.

The mapper uses the existing graph manager, stable module/test IDs, and valid
retained explicit links. Filename-based implementation/test links are inferred and
not evidence-backed; ambiguous matches are omitted. Successful tool file references
can link a requirement to an observed implementation. Evidence links retain actual
requirement/tool-call identities.

Timeline events cover scans, blueprint initialization, adopted requirements,
agent states, and drift evaluation. Reads do not pretend to represent live
filesystem monitoring or streaming agent progress.

## Drift behavior

Production fields are implementations, tests, links, and evidence references;
there is no graph.nodes or generic node_id compatibility shim.

Baselines record feature/task relationships and per-implementation hashes.
Legacy content_hash applies only to a single tracked implementation.

| State | Meaning |
| --- | --- |
| CONFIRMED_STRUCTURAL_DRIFT | Required node/file/recorded relationship removed or reparented |
| POTENTIAL_DRIFT | Related implementation content changed; semantics need verification |
| UNRESOLVED | Required observations/hashes or valid evidence references unavailable |
| NO_DRIFT | Recorded relationships/hashes intact; unrelated file changes ignored |

Structural severance outranks hash changes. Evidence IDs must exist in the graph
and link to the same requirement. This validates references, not semantic proof.
Acceptance-criteria semantic drift and arbitrary-language analysis remain deferred.
Refresh the workspace before evaluating external edits.

## Error codes

Catch ApiError and inspect exc.code. The boundary sanitizes unexpected failures.

- invalid_project_root: nonexistent/non-directory root or agent-root mismatch
- project_state_unavailable: no observed state
- environment_unavailable: no environment/health observations
- unsupported_operation: unconfigured agent or unsupported method
- permission_required: policy prevents explicit approval
- invalid_request: malformed envelope, parameters, or baseline
- request_not_found: unknown agent request
- action_conflict: conflicting IDs or invalid continuation
- service_closed: operation requested after shutdown
- internal_error: unexpected backend failure; inspect backend logs

project_not_found and verification_unavailable remain reserved enum values for
compatibility. No separate project lookup or verification service was introduced.

## Actual execution isolation

Filesystem tools resolve paths under the project root and exclude configured
secret/runtime paths. Checkpoints use contained per-file copies and restore/remove
tracked files, never git reset. Sensitive Python files are excluded from parsing.
Memory uses pattern/key-based redaction, not an exhaustive secret detector.

PythonExecutionTool runs the current backend interpreter in an ordinary subprocess
with project cwd. TestExecutionTool invokes that interpreter's pytest with a timeout.
Processes inherit user privileges and ambient environment. This is NOT an OS sandbox:
approved Python code can access resources beyond cwd. Tool path checks constrain
selected paths, not arbitrary behavior of executed code, and do not eliminate
filesystem race conditions.

No container, restricted OS token, network isolation, project-interpreter switching,
token streaming, live event push, or forceful cancellation is implemented.
Luminous training/inference integration and its placeholder evaluator are outside
this phase. Environment inspection is Python-centric; another project venv may
remain uninspected.
