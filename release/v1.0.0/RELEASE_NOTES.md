# OpenArise IDE v1.0.0 Release Notes

**Release Date:** 2026-11-05  
**Version:** 1.0.0 (Production Release)  
**Target Platform:** Windows 10 / Windows 11 (x64)  
**Architecture:** 64-bit Native PE Executable & Inno Setup Modern Installer  

OpenArise IDE v1.0.0 marks the first official production release of our local-first AI development environment. Designed around an autonomous, agent-centric workflow, OpenArise IDE empowers developers to create complete, working applications using natural language with 100% data privacy and local LLM execution.

---

## What's New in v1.0.0

### 1. Minimalist, Distraction-Free Main Toolbar
- Main toolbar simplified to exactly four essential actions:
  1. **Open Folder**
  2. **New File**
  3. **Save**
  4. **Run Python**
- All advanced capabilities (Testing, Reindexing, Source Control, Extension Manager) remain fully accessible via the top menus and the Command Palette (`Ctrl+Shift+P`).
- Top menu order standardized: `File | View | Run | Tools | AI | Settings | Help`.

### 2. AI Coding Agent V1.0 (Cursor-Level Workflow)
- **Deep Codebase Understanding:**
  - Automatic workspace profiling identifying frameworks, entrypoints, and dependencies.
  - AST-based Python symbol extraction and regex-based JavaScript/TypeScript extraction.
  - Efficient symbol search across functions, classes, and routes.
  - Compact project summaries (~250 tokens) injected into the context window, eliminating token bloat.
- **Cursor-Like File Operations:**
  - `write_files`: Batch multi-file creation in a single round trip.
  - `replace_in_file`: Surgical search-and-replace preserving existing code structure and formatting.
  - Line-range sliced reading for large files.
  - Zero-placeholder policy: Strict post-write validator detects and rejects placeholder comments (`/* Add code here */`).
- **Autonomous Build, Run, Test & Self-Healing:**
  - Automatic runnable detection providing direct browser preview URLs and terminal commands.
  - Self-healing debugger detects syntax errors, writes surgical repairs, and re-verifies automatically.
- **Performance & Streaming:**
  - Live token streaming with real-time UI logging.
  - Per-step context window pruning keeping KV-cache small and prompt evaluation sub-second.
  - Adaptive auto-advancement cuts model invocations by up to 70%.

### 3. Integrated Terminal
- Full PowerShell integration with merged stdout/stderr streaming.
- Process lifecycle management with clean process termination on **Stop**.
- Working directory persistence across tabs and command executions.

### 4. Interactive Diff Review & Safety
- Visual side-by-side / unified Diff Review before changes are finalized.
- Support for Accept All, Reject All, and selective per-file approval.
- Automatic `.bak` backup creation and instant rollback.
- Full support for both Git repositories and non-versioned folders.

### 5. UI Layout Stability
- Completely stable Agent panel layout during live streaming updates.
- Fixed table and timeline heights preventing jumping or unexpected resizing.
- Smart auto-scrolling preserves user scroll position when reviewing older logs.

### 6. Packaging & Deployment
- Single-file portable executable (`OpenAriseIDE.exe`) with embedded Qt, Pygments, and Markdown assets.
- Modern Inno Setup installer (`OpenAriseIDE-Setup-1.0.0.exe`) with desktop/start-menu shortcuts and clean uninstallation.
- Infinity logo branding strictly on title bar and taskbar.

---

## Known Limitations

- **Local Inference Speed:** On systems without dedicated GPU acceleration, `qwen2.5-coder:7b` generates ~10–20 tokens/sec. For faster CPU execution, `qwen2.5-coder:1.5b` can be used.
- **Ollama Dependency:** OpenArise IDE requires Ollama to be installed separately as a prerequisite for AI features.

