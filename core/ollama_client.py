"""
Ollama Client and Worker Threads for OpenArise IDE.
Supports chat streaming, inline completions, model downloads with progress,
model deletion, detailed model metadata, running model inspection (/api/ps),
and authoritative generation metrics extraction for analytics.
"""

from __future__ import annotations
import json
from typing import Any, Callable, Optional

import requests
from PyQt6.QtCore import QThread, pyqtSignal

OLLAMA_URL = "http://127.0.0.1:11434"


class OllamaError(RuntimeError):
    """Raised when Ollama cannot complete a request."""


def format_bytes(num_bytes: Optional[int]) -> str:
    """Formats raw byte counts into human-readable strings (e.g., 4.7 GB)."""
    if num_bytes is None or num_bytes < 0:
        return "Unknown"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:.1f} {unit}" if unit in ("MB", "GB", "TB") else f"{int(num_bytes)} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"


class OllamaClient:
    """HTTP client interface for local Ollama daemon."""

    def __init__(self, base_url: str = OLLAMA_URL, timeout: tuple[int, int] = (5, 300)):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    def check_connection(self) -> tuple[bool, str]:
        """Verifies whether the Ollama server is running and reachable."""
        try:
            resp = self.session.get(f"{self.base_url}/api/tags", timeout=3)
            if resp.status_code == 200:
                count = len(resp.json().get("models", []))
                return True, f"Connected ({count} model{'s' if count != 1 else ''} available)"
            return False, f"Ollama returned HTTP status {resp.status_code}"
        except Exception as exc:
            return False, f"Ollama unavailable at {self.base_url} ({exc})"

    def health(self) -> dict[str, Any]:
        """Fetches /api/tags payload."""
        response = self.session.get(f"{self.base_url}/api/tags", timeout=self.timeout[0])
        response.raise_for_status()
        return response.json()

    def list_models(self) -> list[str]:
        """Returns a list of installed model names."""
        data = self.health()
        return [item.get("name", "") for item in data.get("models", []) if item.get("name")]

    def list_models_detailed(self) -> list[dict[str, Any]]:
        """
        Returns rich metadata for each installed model:
        name, size bytes, formatted size, modified timestamp, family, parameter size, quantization.
        """
        data = self.health()
        detailed_list = []
        for item in data.get("models", []):
            name = item.get("name", "")
            if not name:
                continue
            size = item.get("size", 0)
            details = item.get("details", {}) or {}
            detailed_list.append({
                "name": name,
                "size": size,
                "size_formatted": format_bytes(size),
                "modified_at": item.get("modified_at", ""),
                "digest": item.get("digest", "")[:12] if item.get("digest") else "",
                "family": details.get("family", "") or "Unknown",
                "parameter_size": details.get("parameter_size", "") or "Unknown",
                "quantization_level": details.get("quantization_level", "") or "Unknown",
                "format": details.get("format", "") or "gguf",
            })
        return detailed_list

    def show_model(self, model: str) -> dict[str, Any]:
        """Queries /api/show for full model parameters and template."""
        response = self.session.post(
            f"{self.base_url}/api/show",
            json={"name": model},
            timeout=self.timeout[0]
        )
        response.raise_for_status()
        return response.json()

    def list_running_models(self) -> list[dict[str, Any]]:
        """
        Queries /api/ps to inspect models currently loaded into system RAM/VRAM.
        """
        try:
            response = self.session.get(f"{self.base_url}/api/ps", timeout=3)
            if response.status_code == 200:
                models = response.json().get("models", [])
                out = []
                for m in models:
                    size = m.get("size", 0)
                    vram = m.get("size_vram", 0)
                    out.append({
                        "name": m.get("name", ""),
                        "model": m.get("model", ""),
                        "size": size,
                        "size_formatted": format_bytes(size),
                        "size_vram": vram,
                        "size_vram_formatted": format_bytes(vram),
                        "expires_at": m.get("expires_at", ""),
                    })
                return out
        except Exception:
            pass
        return []

    def delete_model(self, model: str) -> tuple[bool, str]:
        """Deletes a local model via DELETE /api/delete."""
        try:
            response = self.session.delete(
                f"{self.base_url}/api/delete",
                json={"name": model},
                timeout=self.timeout[0]
            )
            if response.status_code == 200:
                return True, f"Model '{model}' successfully deleted."
            return False, f"Failed to delete model: HTTP {response.status_code} ({response.text})"
        except Exception as exc:
            return False, f"Error deleting model: {exc}"

    def pull(self, model: str, progress_callback: Optional[Callable[[dict], None]] = None):
        """Downloads a model streamingly from Ollama model library."""
        with self.session.post(
            f"{self.base_url}/api/pull",
            json={"name": model, "stream": True},
            stream=True,
            timeout=self.timeout,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                    if progress_callback:
                        progress_callback(payload)
                    if payload.get("error"):
                        raise OllamaError(payload["error"])
                except json.JSONDecodeError:
                    continue


class OllamaStreamWorker(QThread):
    token = pyqtSignal(str)
    finished_text = pyqtSignal(str)
    metrics_collected = pyqtSignal(dict)  # Authoritative metrics from final chunk
    failed = pyqtSignal(str)

    def __init__(self, client: OllamaClient, model: str, messages: list[dict], parent=None):
        super().__init__(parent)
        self.client = client
        self.model = model
        self.messages = messages
        self._cancel_requested = False
        self._response = None

    def cancel(self):
        self._cancel_requested = True
        if self._response:
            try:
                self._response.close()
            except Exception:
                pass

    def run(self):
        collected = []
        metrics_payload = None
        try:
            with self.client.session.post(
                f"{self.client.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": self.messages,
                    "stream": True,
                    "keep_alive": "30m",
                },
                stream=True,
                timeout=self.client.timeout,
            ) as response:
                self._response = response
                response.raise_for_status()
                for line in response.iter_lines(decode_unicode=True):
                    if self._cancel_requested or self.isInterruptionRequested():
                        break
                    if not line:
                        continue
                    payload = json.loads(line)
                    if payload.get("error"):
                        raise OllamaError(payload["error"])
                    piece = payload.get("message", {}).get("content", "")
                    if piece:
                        collected.append(piece)
                        self.token.emit(piece)
                    if payload.get("done"):
                        metrics_payload = payload
                        break

            if not (self._cancel_requested or self.isInterruptionRequested()):
                if metrics_payload:
                    self.metrics_collected.emit({
                        "model": self.model,
                        "prompt_eval_count": metrics_payload.get("prompt_eval_count"),
                        "eval_count": metrics_payload.get("eval_count"),
                        "total_duration": metrics_payload.get("total_duration"),
                        "load_duration": metrics_payload.get("load_duration"),
                        "eval_duration": metrics_payload.get("eval_duration"),
                        "prompt_eval_duration": metrics_payload.get("prompt_eval_duration"),
                    })
                self.finished_text.emit("".join(collected))
        except Exception as exc:
            if not (self._cancel_requested or self.isInterruptionRequested()):
                self.failed.emit(f"Ollama request failed: {exc}")


class OllamaGenerateWorker(QThread):
    token = pyqtSignal(str)
    finished_text = pyqtSignal(str)
    metrics_collected = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, client: OllamaClient, model: str, prompt: str, parent=None):
        super().__init__(parent)
        self.client, self.model, self.prompt = client, model, prompt
        self._cancel_requested = False
        self._response = None

    def cancel(self):
        self._cancel_requested = True
        if self._response:
            try:
                self._response.close()
            except Exception:
                pass

    def run(self):
        output = []
        metrics_payload = None
        try:
            with self.client.session.post(
                f"{self.client.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": self.prompt,
                    "stream": True,
                    "keep_alive": "30m",
                },
                stream=True,
                timeout=self.client.timeout,
            ) as response:
                self._response = response
                response.raise_for_status()
                for line in response.iter_lines(decode_unicode=True):
                    if self._cancel_requested or self.isInterruptionRequested():
                        break
                    if not line:
                        continue
                    payload = json.loads(line)
                    if payload.get("error"):
                        raise OllamaError(payload["error"])
                    piece = payload.get("response", "")
                    if piece:
                        output.append(piece)
                        self.token.emit(piece)
                    if payload.get("done"):
                        metrics_payload = payload
                        break

            if not (self._cancel_requested or self.isInterruptionRequested()):
                if metrics_payload:
                    self.metrics_collected.emit({
                        "model": self.model,
                        "prompt_eval_count": metrics_payload.get("prompt_eval_count"),
                        "eval_count": metrics_payload.get("eval_count"),
                        "total_duration": metrics_payload.get("total_duration"),
                        "load_duration": metrics_payload.get("load_duration"),
                        "eval_duration": metrics_payload.get("eval_duration"),
                        "prompt_eval_duration": metrics_payload.get("prompt_eval_duration"),
                    })
                self.finished_text.emit("".join(output))
        except Exception as exc:
            if not (self._cancel_requested or self.isInterruptionRequested()):
                self.failed.emit(f"Generation failed: {exc}")


class OllamaPullWorker(QThread):
    progress = pyqtSignal(str, int)
    completed = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, client: OllamaClient, model: str, parent=None):
        super().__init__(parent)
        self.client, self.model = client, model
        self._cancel_requested = False

    def cancel(self):
        self._cancel_requested = True

    def run(self):
        try:
            def update(payload):
                if self._cancel_requested or self.isInterruptionRequested():
                    raise InterruptedError("Cancelled")
                status = str(payload.get("status", "Downloading"))
                total, done = payload.get("total", 0), payload.get("completed", 0)
                percent = int(done * 100 / total) if total else 0
                self.progress.emit(status, max(0, min(100, percent)))

            self.client.pull(self.model, update)
            if not (self._cancel_requested or self.isInterruptionRequested()):
                self.completed.emit()
        except InterruptedError:
            pass
        except Exception as exc:
            self.failed.emit(f"Model download failed: {exc}")
