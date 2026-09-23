# Integration Handover (Phase 6)

## Overview
This document serves as the final Person 2 handover for the Person 3 UI implementation and Person 1 AI Integration. OpenArise IDE's intelligence layer acts as a strict, read-only boundary between factual project observation and mutating AI operations.

## Architecture Guidelines for Person 3

### 1. Service Facade
Person 3 Desktop/API layer **MUST** consume the single entry-point facade:
`app.api.services.ProjectWorkspaceService(project_root: str, orchestrator: Optional[AgentOrchestrator] = None)`

Do NOT instantiate `ProjectScanner`, `HealthEngine`, or `RequirementDriftDetector` individually in the UI.

### 2. Read Operations
The `ProjectWorkspaceService` provides the following side-effect free, deterministic endpoints/methods returning a typed `SuccessResponse`:
- `get_project_information()`
- `get_project_state()`
- `get_blueprint()`
- `get_requirements()`
- `get_traceability_graph()`
- `get_environment_status()`
- `get_health_report()`
- `get_intelligence_snapshot()`
- `get_timeline()`
- `get_drift_report(baseline_dict)`

These operations NEVER execute project code, NEVER mutate files, and NEVER install dependencies.

### 3. Action Operations (Mutating)
The **only** approved method for executing mutating agent tasks is:
- `request_agent_execution(prompt: str, context_data: Optional[dict] = None)`

This delegates the task to the Person 1 `AgentOrchestrator`. It seamlessly leverages the `ProjectIntelligenceContextAdapter` to inject a bounded, safe project summary without exposing sensitive tokens, overflowing context size, or bypassing `PermissionManager` verification.

### 4. Error Contract
Person 3 UI should anticipate deterministic exceptions thrown as `ApiError`. Catch `ApiError` and inspect `exc.code` against the `ErrorCode` Enum:
- `PROJECT_NOT_FOUND`
- `INVALID_PROJECT_ROOT`
- `PROJECT_STATE_UNAVAILABLE`
- `ENVIRONMENT_UNAVAILABLE`
- `UNSUPPORTED_OPERATION`
- `PERMISSION_REQUIRED`
- `VERIFICATION_UNAVAILABLE`
- `INTERNAL_ERROR`

Raw stack traces must not be leaked to the end-user.

### 5. AI Integration Boundary
The `ProjectIntelligenceContextAdapter` prevents AI hallucination and limits token overhead by compressing the Intelligence Snapshot down into pure summaries (`total_files`, `health_issues`, etc.). Do not bypass the adapter to dump `ProjectState.files` fully into the prompt unless building an explicit retrieval tool. 
