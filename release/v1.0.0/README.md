# OpenArise IDE v1.0.0

OpenArise IDE is a fast, reliable, local-first AI-powered integrated development environment designed to provide a Cursor-level coding workflow with local large language models (such as `qwen2.5-coder:7b`).

---

## System Requirements

- **Operating System:** Windows 10 or Windows 11 (64-bit / x64).
- **Processor:** Modern multi-core Intel or AMD processor (x86-64).
- **Memory (RAM):** 8 GB minimum; 16 GB+ recommended when running local 7B AI models.
- **Disk Space:** ~500 MB for OpenArise IDE; ~5 GB free space for Ollama and `qwen2.5-coder:7b`.
- **AI Backend (Prerequisite):** Local [Ollama](https://ollama.com) installation with at least one coding model installed.

---

## Installation Options

### Option 1: Standard Windows Installer (Recommended)
1. Run `OpenAriseIDE-Setup-1.0.0.exe`.
2. Follow the setup wizard prompts.
3. Select whether to create a Desktop shortcut.
4. Finish installation. OpenArise IDE will be installed to `%LOCALAPPDATA%\Programs\OpenArise IDE` (or Program Files if elevated) and accessible via the Windows Start Menu.
5. To uninstall, use Windows **Settings > Apps > Installed apps** or run `unins000.exe` in the application folder.

### Option 2: Portable Executable
1. Copy `OpenAriseIDE.exe` to any folder of your choice (e.g. `C:\Tools\OpenAriseIDE\`).
2. Double-click `OpenAriseIDE.exe` to launch directly. No installation or administrator privileges required.

---

## Quick Start Guide

1. **Start Ollama Daemon:**
   Ensure Ollama is running in the background. If you haven't installed Ollama yet, see [OLLAMA_SETUP_GUIDE.md](OLLAMA_SETUP_GUIDE.md).
   ```powershell
   ollama run qwen2.5-coder:7b
   ```

2. **Launch OpenArise IDE:**
   Start OpenArise IDE via the Start Menu or executable.

3. **Open Your Project:**
   Click **Open Folder** on the main toolbar to select your workspace.

4. **Give Tasks to the AI Agent:**
   - Switch to the **AI Agent** tab on the right panel.
   - Type your task in natural language (e.g. *"Create a modern responsive task management website with HTML, CSS, and JavaScript using localStorage"*).
   - Click **Run Task** or press Enter.
   - Watch the Agent profile the project, stream tokens in real-time, generate the files, verify them against stubs, and output runtime launch instructions.

5. **Run & Test:**
   - Review any changes in the interactive **Diff Review** window.
   - Launch your application using the **Integrated Terminal** at the bottom (e.g., `python -m http.server 8000` or `python main.py`).

---

## Local-First Privacy Guarantee

OpenArise IDE is 100% local-first:
- Your source code never leaves your computer.
- All AI reasoning is executed entirely on your machine via local Ollama inference.
- Zero telemetry, zero tracking, zero mandatory cloud accounts.

