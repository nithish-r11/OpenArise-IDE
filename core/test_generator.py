from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal
from core.ollama_client import OllamaGenerateWorker

class TestGenerator(QObject):
    generated = pyqtSignal(str, str)
    metrics_collected = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, client, parent=None):
        super().__init__(parent)
        self.client = client
        self.worker = None

    def generate(self, model, source_path, source_code, selected_code=""):
        path = Path(source_path)
        target = path.with_name(f"test_{path.stem}.py")
        subject = selected_code.strip() or source_code
        prompt = (
            "Write comprehensive executable pytest tests for the Python code below. "
            "Return only Python source code, with imports and fixtures as needed. "
            "Do not use markdown fences. Do not invent unavailable external services.\n\n"
            f"Source file: {path.name}\n\n{subject}"
        )
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.requestInterruption()
            self.worker.wait(1000)
        self.worker = OllamaGenerateWorker(self.client, model, prompt, self)
        self.worker.metrics_collected.connect(self.metrics_collected.emit)
        self.worker.finished_text.connect(lambda text: self._save_result(target, text))
        self.worker.failed.connect(self.failed.emit)
        self.worker.start()

    def _save_result(self, target, text):
        try:
            cleaned = text.strip()
            if cleaned.startswith("```"):
                lines = cleaned.splitlines()
                if lines and lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                cleaned = "\n".join(lines)
            if not cleaned.strip():
                raise ValueError("The model returned an empty test file.")
            target.write_text(cleaned.rstrip() + "\n", encoding="utf-8")
            self.generated.emit(str(target), cleaned)
        except Exception as exc:
            self.failed.emit(f"Could not save generated tests: {exc}")
