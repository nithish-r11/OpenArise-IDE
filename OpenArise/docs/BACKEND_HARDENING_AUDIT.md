# Backend integration hardening audit

Completed: 2026-09-24. Scope: backend integration only.

## Exact validation result

| Metric | Result |
| --- | ---: |
| Total collected | 161 |
| Passed | 161 |
| Failed | 0 |
| Skipped | 0 |
| Warnings | 0 |
| Original tests retained | 88 |
| Added hardening cases | 73 |
| Last full-suite duration | 10.10 seconds |

Runtime: Windows, existing ai-engine/.venv, Python 3.13.5, pytest 9.1.1.
Full suite executed offline with mocked LLMs and real production backend objects.
File writes and actual Python/pytest execution occurred only in temporary projects.
The original default-root orchestrator tests were isolated using a temporary cwd.
Bytecode was disabled in the parent and subprocesses; pytest's cache provider was
disabled and warnings were promoted to errors.

Additional checks:
- All 88 original top-level test functions remain present.
- The three original drift cases and the intelligence-service fixture now use
  production graph objects instead of test-only graph.nodes substitutes.
- All 124 application/test/support Python files parse.
- git diff --check passed.
- requirements.txt is unchanged; no dependency installation occurred.
- No staged changes, commits, or pushes were created.

### Test coverage added

| New test module | Collected cases | Coverage |
| --- | ---: | --- |
| test_agent_integration.py | 21 | Real tools, request/result IDs, requirements/evidence/gate, ASK/approve/resume/deny/cancel, replay/conflicts, stale test proof |
| test_backend_contract.py | 11 | Envelopes, allowlist, JSON validation, action lifecycle/events, replay, sanitized errors, shutdown |
| test_hardening_security.py | 13 | Root containment, secret paths, checkpoints, recovery tool/retest permissions, duplicate IDs, installation blocking, redaction |
| test_verification_integration.py | 9 | Failed facts, evidence strength, gate precedence, stale references, real AST checks, report counts |
| test_workspace_integration.py | 19 | Read-only assembly, stable mapper, actual context prompt, production drift models, evidence/baseline integration |
| Total | 73 | All passing |

## Defects fixed

1. **Undefined tool-call reference:** orchestration now consistently uses the
   retained ToolCall, preserves call IDs, and retains ToolResults through failures.
   Exceptions, nonzero exit codes, and explicit failed outputs are not success.

2. **Permission continuation:** exact pending actions and request IDs are retained.
   Approve records permission; resume rechecks it and executes without another LLM
   action-generation call. Denial/cancellation revoke approval. New work cannot
   overwrite pending work; conflicting/replayed requests cannot silently reexecute.

3. **Verification wiring:** user requirements reach the generation prompt, evidence
   ledger, independent verifier, and CompletionGate. Evidence associations use
   requirement IDs. Failed execution contradicts completion. Stale/invalid evidence
   cannot pass the gate, and severity precedence is independent of list order.
   Later mutation invalidates prior passing test proof until a fresh passing test.
   Completion reports count actual test tool invocations and recovery attempts.

4. **Project intelligence context:** the adapter's bounded allowlisted summary now
   reaches the actual generation prompt through the existing ContextManager.
   Caller context cannot overwrite the facade's factual summary. Raw repository
   content, unknown nested fields, and raw recent tool outputs are excluded.

5. **Drift compatibility:** drift uses real implementation IDs, production graph
   fields, feature/task links, evidence references, and per-implementation hashes.
   Removed relationships are structural drift, related modifications are potential
   drift, unrelated changes are ignored, and missing facts/references are unresolved.

6. **Workspace assembly:** the facade invokes the existing mapper and shares its
   graph manager, retains node identities, assembles environment/health/snapshots,
   adopts agent requirements/evidence, records timeline events, and captures usable
   requirement baselines. Observation-only tests prove no filesystem mutation or
   project subprocess execution.

7. **Current Person 3 contract:** integration handover and README document actual
   methods, lifecycle, approvals, verification, context, drift, errors, and isolation.
   Historical Person 1 material is explicitly marked as superseded.

8. **Framework-independent boundary:** BackendService adds typed request/response/
   error envelopes, an explicit dispatch allowlist, recorded events, serialized
   execution, in-process replay protection, and shutdown behavior. No server exists.

9. **Permission and containment hardening:** recovery checks actual tool permissions,
   separately checks validation permission, rejects duplicate call IDs, and rechecks
   permission immediately before execution. Automatic dependency installation is
   blocked. File/checkpoint paths use resolved containment, secret paths are
   excluded, and new checkpointed files can be removed on rollback. Sensitive
   Python files are not parsed; nested secret fields are redacted.

## Architecture and scope confirmations

- Person 1 architecture is preserved: AgentOrchestrator still composes the existing
  LLM provider, ContextManager, tool registry, PermissionManager, failure/recovery
  components, memory, requirement extractor, evidence ledger, verifier, and gate.
- PermissionManager remains authoritative for tool execution and recovery validation.
  Production callers must keep test_mode=False.
- CompletionGate remains the final verification authority.
- No duplicate context, project, blueprint, requirement, graph, health, intelligence,
  evidence, or recovery subsystem was introduced. The new dispatcher wraps the
  existing facade rather than implementing backend logic again.
- No FastAPI, Electron, Tauri, transport server, new dependency, or live Ollama test.
- No commit or GitHub push. Work stops at this backend hardening phase.

## Remaining known limitations

- One generated action per request; no continuous replanning loop.
- Pending work, responses, idempotency caches, graph, blueprint, and timeline are
  in memory. No crash-safe replay, durable continuation, or cache retention policy.
- Cancellation applies to pending work; synchronous in-flight calls cannot be
  interrupted. Events are recorded, not streamed live. No filesystem watcher.
- Permission-blocked recovery plans do not have a separate resumable approval API.
  Earlier failed evidence remains contradictory even if recovery later succeeds.
- Requirement extraction is conservative text tracking. Test success is limited to
  tested behavior, not proof of arbitrary semantic requirements. Legacy manually
  supplied direct TEST_PASS evidence remains trusted backend input; no client
  evidence-injection API is exposed.
- Blueprint features/tasks are not generated automatically; desktop authoring APIs
  remain deferred. Static project analysis is primarily Python-specific, and other
  project virtual environments may remain uninspected.
- Drift checks recorded relationships/hashes/references, not semantic acceptance
  criteria. No automatic baseline persistence.
- Subprocesses inherit normal user privileges/environment and use the backend
  interpreter with project cwd. There is NO OS sandbox, restricted token, network
  isolation, or project-interpreter switching. Path checks cannot constrain
  arbitrary approved Python code or eliminate filesystem races.
- Secret redaction is pattern/key-based, not exhaustive.
- Luminous training/inference integration and its placeholder evaluation remain
  outside this phase. app.main remains a logging placeholder.

## Modified and created files

The manifest below includes every changed tracked file and every new file in this
phase, including this audit. No files were deleted.

**32 modified files; 9 created files; 41 files total.**

| Status | File |
| --- | --- |
| Modified | [ai-engine/HANDOVER.md](../ai-engine/HANDOVER.md) |
| Modified | [ai-engine/INTEGRATION_CONTRACT.md](../ai-engine/INTEGRATION_CONTRACT.md) |
| Modified | [ai-engine/README.md](../ai-engine/README.md) |
| Modified | [ai-engine/app/agent/orchestrator.py](../ai-engine/app/agent/orchestrator.py) |
| Modified | [ai-engine/app/agent/state.py](../ai-engine/app/agent/state.py) |
| Modified | [ai-engine/app/api/models.py](../ai-engine/app/api/models.py) |
| Modified | [ai-engine/app/api/services.py](../ai-engine/app/api/services.py) |
| Modified | [ai-engine/app/blueprint/requirements.py](../ai-engine/app/blueprint/requirements.py) |
| Modified | [ai-engine/app/context/adapter.py](../ai-engine/app/context/adapter.py) |
| Modified | [ai-engine/app/context/manager.py](../ai-engine/app/context/manager.py) |
| Modified | [ai-engine/app/intelligence/drift.py](../ai-engine/app/intelligence/drift.py) |
| Modified | [ai-engine/app/intelligence/models.py](../ai-engine/app/intelligence/models.py) |
| Modified | [ai-engine/app/memory/redact.py](../ai-engine/app/memory/redact.py) |
| Modified | [ai-engine/app/memory/store.py](../ai-engine/app/memory/store.py) |
| Modified | [ai-engine/app/models/schemas.py](../ai-engine/app/models/schemas.py) |
| Modified | [ai-engine/app/project/scanner.py](../ai-engine/app/project/scanner.py) |
| Modified | [ai-engine/app/project/state.py](../ai-engine/app/project/state.py) |
| Modified | [ai-engine/app/recovery/checkpoint.py](../ai-engine/app/recovery/checkpoint.py) |
| Modified | [ai-engine/app/recovery/engine.py](../ai-engine/app/recovery/engine.py) |
| Modified | [ai-engine/app/recovery/planner.py](../ai-engine/app/recovery/planner.py) |
| Modified | [ai-engine/app/tools/fs.py](../ai-engine/app/tools/fs.py) |
| Modified | [ai-engine/app/tools/permissions.py](../ai-engine/app/tools/permissions.py) |
| Modified | [ai-engine/app/traceability/graph.py](../ai-engine/app/traceability/graph.py) |
| Modified | [ai-engine/app/traceability/mapper.py](../ai-engine/app/traceability/mapper.py) |
| Modified | [ai-engine/app/verification/drift.py](../ai-engine/app/verification/drift.py) |
| Modified | [ai-engine/app/verification/engine.py](../ai-engine/app/verification/engine.py) |
| Modified | [ai-engine/app/verification/evidence.py](../ai-engine/app/verification/evidence.py) |
| Modified | [ai-engine/app/verification/gate.py](../ai-engine/app/verification/gate.py) |
| Modified | [ai-engine/app/verification/requirements.py](../ai-engine/app/verification/requirements.py) |
| Modified | [ai-engine/tests/test_intelligence_drift.py](../ai-engine/tests/test_intelligence_drift.py) |
| Modified | [ai-engine/tests/test_intelligence_service.py](../ai-engine/tests/test_intelligence_service.py) |
| Modified | [docs/INTEGRATION_HANDOVER.md](INTEGRATION_HANDOVER.md) |
| Created | [ai-engine/app/api/backend.py](../ai-engine/app/api/backend.py) |
| Created | [ai-engine/tests/hardening_helpers.py](../ai-engine/tests/hardening_helpers.py) |
| Created | [ai-engine/tests/test_agent_integration.py](../ai-engine/tests/test_agent_integration.py) |
| Created | [ai-engine/tests/test_backend_contract.py](../ai-engine/tests/test_backend_contract.py) |
| Created | [ai-engine/tests/test_hardening_security.py](../ai-engine/tests/test_hardening_security.py) |
| Created | [ai-engine/tests/test_verification_integration.py](../ai-engine/tests/test_verification_integration.py) |
| Created | [ai-engine/tests/test_workspace_integration.py](../ai-engine/tests/test_workspace_integration.py) |
| Created | [docs/BACKEND_HARDENING_AUDIT.md](BACKEND_HARDENING_AUDIT.md) |
| Created | [docs/BACKEND_PROCESS_CONTRACT.md](BACKEND_PROCESS_CONTRACT.md) |
