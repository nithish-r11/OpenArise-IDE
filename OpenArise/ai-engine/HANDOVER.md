# Person 1 Handover: AI & Agent Engine (Phases 1-7)

This document serves as the official handover artifact for the AI Engine layer of OpenArise IDE, completed in Phases 1-7. It outlines the responsibilities, architecture, directories, contracts, and known limitations to allow Person 2 (Backend/Services) and Person 3 (Frontend/UI) to seamlessly integrate with the engine.

## Person 1 Responsibilities (Completed)
- Built the autonomous agent execution pipeline (`app/agent/orchestrator.py`).
- Integrated local LLM inference through Ollama abstractions (`app/llm/ollama.py`).
- Implemented state tracking, tool registries, and safe, permission-gated execution boundaries (`app/tools/`).
- Designed failure detection, root cause analysis, and loop prevention (`app/failures/`).
- Built the Autonomous Recovery Engine, capable of sandboxing fixes and rollback (`app/recovery/`).
- Implemented persistent project-isolated Failure Memory using SQLite (`app/memory/`).
- Developed the Independent Verification Engine with evidence ledgers and a strict Completion Gate (`app/verification/`).
- Prepared the foundational architecture and JSONL datasets for the planned Luminous 1.1 reliability model (`app/luminous/`).

## Architecture & Directory Structure
The AI Engine operates deterministically unless LLM reasoning is required.
```
ai-engine/
├── app/
│   ├── main.py              # Engine entry point (CLI or service interface)
│   ├── models/              # Pydantic schemas (State, Failures, Memory, Verification)
│   ├── agent/               # AgentOrchestrator and ContextManager
│   ├── llm/                 # LLMProvider abstractions (Ollama, Mock, Luminous)
│   ├── tools/               # ToolRegistry, Execution, Filesystem, and PermissionManager
│   ├── failures/            # FailureDetector, RootCauseAnalyzer, HistoryManager
│   ├── recovery/            # RecoveryEngine, Planner, CheckpointManager, Policy
│   ├── memory/              # SQLiteMemoryStore, SecretRedactor, MemoryManager
│   ├── verification/        # IndependentVerifier, EvidenceLedger, CompletionGate
│   └── luminous/            # Dataset pipelines and Evaluation Framework
└── tests/                   # 44 passing offline pytest suite
```

## Critical Module Behaviors
- **Orchestrator**: Drives the main loop (`process_request`). Will transition to `COMPLETED` when finished, but returns status `"success"` only if the Completion Gate evaluates to `VERIFIED`.
- **Tools**: Untrusted LLM parameters are strictly sandboxed. `PermissionManager` enforces `ASK` or `DENY` states safely.
- **Failures**: Normalize signatures to detect infinite loops.
- **Recovery**: Creates a `.openarise/checkpoints/` snapshot before making any changes. Rolls back on failed verification.
- **Memory**: Stores redacted records in `.openarise/memory/memory.sqlite`. Search is isolated per project ID.
- **Verification**: Does not trust the LLM. AST verification or exact `TEST_PASS` evidence is required.

## Test Command
The suite contains 44 offline tests requiring no active Ollama server.
```bash
python -m venv venv
# Activate virtual environment
pip install -r requirements.txt
pytest tests/
```

## Known Limitations & Deferred Features
1. **Luminous 1.1**: The model is NOT trained. The provider abstraction exists, and datasets can be generated from SQLite failure logs, but the actual specialized local checkpoint is a future phase.
2. **Verification Features**: Currently deterministic checks are limited to File Existence, Pytest outputs, and Python AST Symbol checks. More complex semantic validations are deferred.
3. **Advanced Security UI**: The PermissionManager `ASK` workflow returns `permission_required` and pauses. It waits for UI integration (Person 3) via Person 2's backend.
4. **Persistent Project State**: Person 2 is responsible for persisting global project states outside of the `.openarise/` AI metadata folder (if required).
