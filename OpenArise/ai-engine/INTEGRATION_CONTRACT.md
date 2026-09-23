# Integration Contract

This document defines the strict contracts and boundaries between Person 1 (AI Engine), Person 2 (Backend Services), and Person 3 (Frontend UI).

## Person 1 ↔ Person 2 (AI Engine to Backend)

### 1. Request / Response Flow
Person 2 will wrap the `AgentOrchestrator` in a web framework (e.g., FastAPI, Tauri Rust Backend).
- **Input**: Person 2 submits an `AgentRequest(prompt="...", context_data={...})` to `process_request()`.
- **Output**: Person 1 returns an `AgentResponse` containing:
  - `status`: `"success"`, `"unverified"`, or `"failure"`.
  - `message`: User-friendly string.
  - `current_state`: (e.g. `COMPLETED`, `IDLE`).
  - `data`: A dictionary containing `tool_calls`, `tool_results`, and the full `verification` gate result.

### 2. Tool Approval Flow (PermissionManager)
When a high-risk tool (`RiskLevel.WRITE`, `RiskLevel.EXECUTE`) is invoked, the `PermissionManager` (if configured to `test_mode=False` and policy is `ASK`) will deny immediate execution.
- **Event**: The Orchestrator will yield a `ToolResult` with `success=False` and `error="permission_required"`.
- **Backend Action**: Person 2 must capture this state, pause the AI thread, and emit an event to the frontend (Person 3) asking for user approval. Once approved, the backend re-invokes the orchestrator with the updated permission policy.

### 3. Events / Streams
For long-running tasks, Person 2 should observe the `AgentOrchestrator.state` and `execution_state.history`.
- Emit WebSocket events when the state transitions (`PLANNING` -> `EXECUTING` -> `RECOVERING`).
- Stream the LLM tokens directly from the `LLMProvider` if a streaming interface is desired (Person 2 must extend the provider for yielding chunks).

## Person 1 ↔ Person 3 (AI Engine to Frontend)

*Person 3 does not interact with Person 1 directly. All communication is routed through Person 2.*

### 1. Data Structures Expected by UI
Person 3 must build UI components to render:
- **Requirements List**: Displayed from `gate_result["requirement_results"]`. Visual indicators for `VERIFIED` (Green check), `INCONCLUSIVE` (Yellow dash), `NOT_VERIFIED` (Red X).
- **Failure Memory Dashboard**: Person 3 can query `MemoryManager.get_statistics()` (via Person 2) to display charts of total failures, successful recoveries, and rollbacks.
- **Evidence Ledgers**: The UI should display the exact `source` (e.g. `pytest`, `main.py`) when a requirement is clicked.

### 2. Error Handling Expectations
- If the AI returns `unverified`, the UI should NOT show a giant green "SUCCESS!" banner. It should say "Completed, but requires manual review" or similar, surfacing the missing evidence.
- If the AI encounters a critical framework error, it returns `status="failure"`, and the UI should display the exact `AgentResponse.message`.
