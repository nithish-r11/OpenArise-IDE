# OpenArise IDE Troubleshooting Guide

This guide covers common issues and their solutions when running OpenArise IDE v1.0.0.

---

## 1. AI Connection Issues

### Symptom: Status bar shows "Ollama: Disconnected"
- **Cause:** The local Ollama daemon is not running on `http://127.0.0.1:11434`.
- **Solution:**
  1. Open a PowerShell or Command Prompt terminal.
  2. Run `ollama serve`.
  3. In OpenArise IDE, select **AI > Refresh Models** from the top menu or wait a few seconds for the automatic periodic background health check to reconnect.

### Symptom: "No models available" in dropdown
- **Cause:** Ollama is running, but no models have been downloaded yet.
- **Solution:**
  1. Open PowerShell and run:
     ```powershell
     ollama pull qwen2.5-coder:7b
     ```
  2. Return to OpenArise IDE and click the refresh button next to the model dropdown or restart the IDE.

### Symptom: Ollama connection refused (Port 11434)
- **Cause:** Another service is blocking port 11434, or firewall/proxy restrictions are active.
- **Solution:**
  Check whether port 11434 is in use:
  ```powershell
  Get-NetTCPConnection -LocalPort 11434
  ```
  Ensure Ollama is permitted to bind to localhost.

---

## 2. Integrated Terminal Issues

### Symptom: Command output does not stream in real-time
- **Cause:** Windows PowerShell buffering or process freeze.
- **Solution:**
  1. Click **Clear** in the terminal toolbar to reset output buffer.
  2. If a process is hung, click **Stop** (red square) to terminate the active command.
  3. The terminal uses your system's default PowerShell (`powershell.exe`).

### Symptom: Port already in use when starting local web server
- **Cause:** A previously started `python -m http.server` was not terminated.
- **Solution:**
  Find and kill the process:
  ```powershell
  Get-Process python | Stop-Process -Force
  ```
  Or stop the process directly from the Integrated Terminal using **Stop**.

---

## 3. AI Agent Tasks & File Modifications

### Symptom: Agent task takes several minutes
- **Explanation:** When running `qwen2.5-coder:7b` locally on CPU without dedicated GPU acceleration, token generation typically averages 10–20 tokens/second. A multi-file task generating 3,000+ tokens will take 2–5 minutes.
- **Recommendation:**
  - For maximum performance, run on a system with an NVIDIA RTX GPU (Ollama automatically offloads layers to GPU VRAM).
  - On low-spec laptops, switch to `qwen2.5-coder:1.5b` for 4x faster response times.

### Symptom: Diff Review shows changes I want to reject
- **Solution:**
  The **Diff Review** dialog allows selective file acceptance. Simply uncheck files you do not wish to write, or click **Reject All** to roll back all staged changes cleanly. Backups of modified files are automatically preserved in `.bak` format.

---

## 4. Packaging and File Locations

- **Settings & Theme Persistence:** Stored in `%APPDATA%\OpenArise_IDE\settings.json`.
- **Installed Application Path:** `%LOCALAPPDATA%\Programs\OpenArise IDE\`
- **Crash Recovery Snapshots:** Stored in `%TEMP%\openarise_recovery\`.

