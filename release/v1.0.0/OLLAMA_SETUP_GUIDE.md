# Ollama Setup & Model Guide for OpenArise IDE

OpenArise IDE relies on **Ollama** as its local AI engine. Ollama must be installed and running on your system to enable AI Chat and autonomous AI Agent capabilities.

---

## 1. Installing Ollama on Windows

1. Download the official Windows installer from:  
   **[https://ollama.com/download/windows](https://ollama.com/download/windows)**
2. Run `OllamaSetup.exe` and complete the installation.
3. Once installed, Ollama runs automatically as a Windows background tray application.
4. Verify the server is running by opening PowerShell and executing:
   ```powershell
   ollama --version
   ```

---

## 2. Downloading Recommended Coding Models

OpenArise IDE is optimized for `qwen2.5-coder:7b`. It provides the best balance of code generation precision, instruction following, and speed.

Run the following command in PowerShell:

```powershell
# Recommended Default (Primary Coding & Agent Model)
ollama pull qwen2.5-coder:7b
```

### Alternative Models Supported

| Model Tag | Parameters | Recommended System Specs | Description |
|---|---|---|---|
| `qwen2.5-coder:7b` | 7.6 Billion | 16 GB RAM / 6GB+ VRAM | **Recommended Default**: Best multi-file agent performance, syntax repair, and tool calling. |
| `qwen2.5-coder:1.5b` | 1.5 Billion | 8 GB RAM / Any CPU | Ultra-fast, lightweight model for low-spec laptops. Good for simple edits. |
| `deepseek-coder:6.7b` | 6.7 Billion | 16 GB RAM / 6GB+ VRAM | High-accuracy Python and algorithm coding model. |
| `llama3.2:3b` | 3.2 Billion | 8 GB–12 GB RAM | General conversation and quick explanations. |

To download any alternative model:
```powershell
ollama pull qwen2.5-coder:1.5b
```

---

## 3. Verifying Ollama Health & Connection

Open your web browser or run PowerShell:
```powershell
curl http://127.0.0.1:11434/api/tags
```
You should see a JSON response listing your installed models.

---

## 4. Selecting Models inside OpenArise IDE

1. Launch **OpenArise IDE**.
2. Look at the status bar at the bottom:
   - Green indicator: **Ollama: Connected (X models available)**
   - Red indicator: **Ollama: Disconnected**
3. In both the **AI Chat** and **AI Agent** panels, use the model dropdown to select your active model (e.g., `qwen2.5-coder:7b`).
4. The IDE remembers your model selection across sessions.

---

## 5. Offline Operation

If Ollama is not installed or the daemon is stopped:
- OpenArise IDE remains fully functional as a fast code editor, file explorer, and terminal.
- The AI status bar indicates that Ollama is offline.
- You can start Ollama at any time by running `ollama serve` or launching Ollama from the Windows Start Menu, and OpenArise IDE will automatically reconnect without requiring a restart.

