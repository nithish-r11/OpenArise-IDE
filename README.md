# OpenArise IDE

Standalone local-first Python desktop coding assistant powered by Ollama.

## Requirements
- Windows 10/11 (64-bit)
- Python 3.10+
- Ollama installed from https://ollama.com
- At least one model, e.g. `ollama pull deepseek-coder` or `ollama pull qwen2.5-coder`

## Run from source
```powershell
py -3.10 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

## Build a single-file executable
```powershell
python build_exe.py
```
The executable is written to `dist\OpenAriseIDE.exe`. Build on Windows for a Windows executable.

## Features
- Project tree and multi-tab editor with line numbers and basic Python highlighting
- Ollama model discovery and streaming chat/generation
- Project-wide text indexing with common generated/vendor directories excluded
- Explicit active-file, selected-code, `@file(path)` and `@codebase` context
- Selection-based inline AI replacement (Ctrl+K / Ctrl+I)
- Generated pytest file creation

## Operational notes
- Ollama must be installed and running locally. OpenArise does not bundle model weights.
- The index is held in memory and rebuilt when requested; it is not a semantic vector database.
- Keep projects you open trusted. AI-generated code should be reviewed before execution.
- The initial editor includes lightweight Python syntax highlighting. Other file types remain editable as plain text.
- For large projects, tune `MAX_FILE_BYTES` and prompt context limits in `core/context_manager.py`.
- The app does not execute generated code or tests automatically.
