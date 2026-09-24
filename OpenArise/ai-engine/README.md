# OpenArise backend

OpenArise currently contains the Person 1 AI engine and Person 2 project intelligence
backend, with an integration-hardening layer for future Person 3 desktop work.
No desktop application or transport server is implemented.

## Current contracts

- [Person 3 integration handover](../docs/INTEGRATION_HANDOVER.md)
- [Framework-independent backend process contract](../docs/BACKEND_PROCESS_CONTRACT.md)
- [Hardening audit and file manifest](../docs/BACKEND_HARDENING_AUDIT.md)

Use ProjectWorkspaceService for workspace observation and agent lifecycle methods.
BackendService adds an allowlisted, typed in-process command boundary suitable for
a future process wrapper. It opens no HTTP/WebSocket/stdio listener.

## Capabilities

- Read-only Python project scanning, AST metadata, dependencies, health, blueprint
  scaffolding, stable traceability mapping, snapshots, timeline, and drift checks.
- Synchronous Ollama text/structured inference and registered engineering tools.
- Retained permission-required actions with separate approve/resume, deny/cancel,
  stable request/tool IDs, and in-process replay protection.
- Requirement-associated evidence and a CompletionGate that distinguishes verified,
  unverified, failed, denied, and cancelled work.
- Existing failure diagnosis, recovery planning, per-file checkpoints, and
  project-local SQLite failure memory.

Tool paths are checked against the project root, and configured secret files are
excluded. Execution uses ordinary subprocesses with the backend interpreter and
project cwd; there is no OS sandbox. PermissionManager is authoritative for primary
tools and recovery validation. Automatic dependency installation is disabled.

## Configuration and dependencies

Declared dependencies remain pydantic, pydantic-settings, requests, and pytest.
No dependency was added during hardening. The existing local .venv is used for tests.

Environment settings, also shown in .env.example:
- OLLAMA_HOST: http://localhost:11434
- OLLAMA_MODEL: llama3
- LUMINOUS_MODEL: Luminous 1.1
- LOG_LEVEL: INFO

Configure an LLM provider and explicitly register permitted tools when constructing
AgentOrchestrator. Observation-only ProjectWorkspaceService needs neither an agent
nor Ollama. app.main remains an initialization/logging placeholder, not a server.

## Offline validation

Tests use temporary projects and mocked LLM responses; no live Ollama model is used.
The suite includes the original 88 tests plus backend hardening regression tests.
See the audit for the exact validated total and result.

The hardening validation runs the existing .venv interpreter with bytecode disabled
and pytest arguments: -p no:cacheprovider -W error -ra --tb=short.
Use a disposable working directory with this ai-engine directory on sys.path:
legacy orchestrator tests default project_root to cwd and initialize .openarise.
Set PYTHONDONTWRITEBYTECODE=1 so nested test subprocesses also avoid bytecode caches.

## Limits

One structured action is generated per request; continuation resumes that action,
not an autonomous replanning loop. Pending work, graph, blueprint, timeline, and
command caches are in memory. No watcher, live token/event stream, in-flight
cancellation, or durable restart recovery is provided. Requirement extraction is
conservative and test success proves only the behavior those tests exercise.
Blocked recovery plans do not yet have their own resumable approval workflow.
Luminous model training/integration and its placeholder evaluator remain deferred.

The historical Person 1 HANDOVER.md is retained as background. Current behavior,
error codes, method names, and execution limitations are in the contracts above.
