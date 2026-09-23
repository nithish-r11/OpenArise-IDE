# OpenArise AI Engine - Step 2

## What the AI Engine Does
The AI Engine is the foundational intelligence layer for OpenArise IDE. It handles reasoning, execution, contextual understanding, and interactions with underlying LLM models.

## Current Architecture
The current implementation provides the core foundational abstractions and a concrete execution pipeline:
- **`app/llm/ollama.py`**: Concrete implementation of `LLMProvider` using HTTP requests to local Ollama.
- **`app/agent/orchestrator.py`**: The minimal Agent Orchestrator handling the `Request -> Context -> LLM -> Response` loop.
- **`app/agent/state.py`**: Strongly typed agent states.
- **`app/context/manager.py`**: Simple and extensible context manager to track the state of requests, terminal output, and tools.
- **`app/tools/base.py`**: Safe tool abstraction and registry.
- **`app/models/schemas.py`**: Strongly typed schemas for agent interactions, failure events, and states using Pydantic.

## Agent States
- `IDLE`
- `THINKING`
- `PLANNING`
- `EXECUTING`
- `OBSERVING`
- `FAILED`
- `RECOVERING`
- `VERIFYING`
- `COMPLETED`

## Ollama Setup and Configuration
The AI Engine can interact with a locally running Ollama instance. It uses the following environment variables (which can be set in `.env`):
- `OLLAMA_HOST`: The base URL for the Ollama server (default: `http://localhost:11434`).
- `OLLAMA_MODEL`: The local model to use for the agent (default: `llama3`).
- `LUMINOUS_MODEL`: The specialized reliability model for future steps (default: `Luminous 1.1`).

## Tool Execution and Sandbox
The Agent can safely execute the following software-engineering tools within the project sandbox:
- **ProjectInspectorTool**: Traverses project directory structure with depth limits and ignores hidden/large directories.
- **ReadFileTool**: Reads files within the project root. Rejects sensitive files (e.g. `.env`, `credentials`) and path traversals.
- **WriteFileTool**: Safely creates or replaces files. Prevent silent overwriting without explicit permission.
- **EditFileTool**: Performs exact-match string replacements to prevent ambiguous edits.
- **PythonExecutionTool**: Executes python scripts via subprocess with strict timeouts and output capture.
- **TestExecutionTool**: Safely runs `pytest` for the project.

## Permission System
A `PermissionManager` handles tool permissions across three risk levels:
- **READ**: Allowed by default (Inspection, Reading).
- **WRITE**: Requires explicit approval (Writing, Editing).
- **EXECUTE**: Requires explicit approval (Python/Test execution).

## How to Run the AI Engine
Ensure Ollama is running locally, and start the application. (Full application entrypoints will be provided in a later step.)
```bash
python -m app.main
```

## Failure Detection & Root Cause Analysis
OpenArise automatically monitors ToolResults for failures (timeouts, syntax errors, permission denied, etc.).
- **Deterministic Detection**: Common errors like `ModuleNotFoundError` are deterministically parsed into strong types (`IMPORT_ERROR`).
- **Loop Detection**: A `FailureHistoryManager` bounds and tracks recent failures, identifying when the Agent is stuck in a loop trying the same broken action.
- **LLM-Assisted Diagnosis**: If deterministic classification is insufficient, the system falls back to the LLM to analyze the traceback and output a structured `DiagnosisResult` (unless evidence is missing, in which case it reports LOW confidence).

## Autonomous Recovery Engine (Phase 5)
When a failure is diagnosed, the Autonomous Recovery Engine dynamically plans and executes a safe fix.
- **Recovery Planner**: Combines deterministic rules (e.g. executing a sandboxed script to install dependencies) with LLM-assisted code repair (for syntax and logic errors).
- **Checkpoints & Rollbacks**: A sandbox-aware `CheckpointManager` snapshots modified files *before* a fix is applied. If the validation fails, it safely rolls back the changes. It avoids aggressive git resets to protect unrelated user progress.
- **Permission Bounded**: Every recovery action strictly maps to the safe tools defined in Phase 3. Any `WRITE` or `EXECUTE` action must clear the `PermissionManager`.
- **Targeted Retesting**: Automatically executes targeted tests to verify the fix.
- **Loop Protection**: Guided by `RecoveryPolicyManager` to block infinite retry loops and limit repeated attempts.

## Persistent Failure Memory (Phase 6)
OpenArise learns from its mistakes using a project-scoped, persistent SQLite memory.
- **Redaction**: A regex-based Secret Redactor strips API keys, tokens, and passwords before storing any memory records.
- **Memory Retrieval**: The `MemoryManager` indexes failures by deterministic signature. Before attempting a new recovery, the `RecoveryPlanner` searches the database and injects the history of past attempts into the LLM context.
- **Project Isolation**: Memories are strictly isolated to the current `.openarise` project database.
- **Luminous Training Data**: Automatically structures and exports successful, verified recoveries to a `.jsonl` file for future LLM fine-tuning.

## Independent Verification (Phase 7)
OpenArise validates requirements using an independent verification engine before declaring a task completed.
- **Requirement Extractor**: Parses the user's initial prompt into structured, trackable requirements.
- **Evidence Ledger**: Accumulates file existence, AST symbol availability, test outputs, and tool logs as evidence records.
- **Independent Verifier**: Evaluates requirements against collected evidence. It doesn't blindly trust the LLM; missing evidence forces an `INCONCLUSIVE` status.
- **Completion Gate**: Blocks the Orchestrator from falsely declaring success if the Independent Verifier determines the project isn't fully verified.
- **Luminous 1.1 Architecture**: Introduces the foundational provider abstraction for the upcoming Luminous 1.1 reliability model. Prepares JSONL dataset pipelines for offline model fine-tuning.

## Mock / Offline Testing
The tests cover the Agent Orchestrator, Ollama Provider, context management, tool sandbox security, failure detection, permissions, the autonomous recovery engine, persistent memory, and the independent verification engine without needing an active Ollama instance. They use pytest temporary directories to prevent any destructive file operations on the real codebase.

```bash
python -m venv venv
# Activate virtual environment
pip install -r requirements.txt
pytest tests/
```
*(Currently exactly 44 tests passing)*

## Current Limitations (Intentionally Deferred)
- **Luminous 1.1 Integration**: Setup for Luminous 1.1 is configured, and JSONL data can be exported, but model training and full integration will be done in the future.
- **Advanced Security UI**: The PermissionManager `ASK` flow currently waits for UI integration (Person 3).
