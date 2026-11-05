import os
import re
import shutil
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QProcess, QProcessEnvironment, pyqtSignal
from PyQt6.QtGui import QFont, QTextCursor, QColor
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPlainTextEdit,
    QLineEdit,
    QPushButton,
    QLabel,
    QToolButton,
)

ANSI_ESCAPE_REGEX = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


class TerminalInputLineEdit(QLineEdit):
    """
    Command input line with Up/Down arrow history navigation and Enter execution.
    """
    command_submitted = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.history = []
        self.history_index = -1
        self._temp_input = ""
        self.setPlaceholderText("Enter command (e.g. python, pytest, git)…")
        self.setStyleSheet(
            "QLineEdit {"
            "  background: #181b22; color: #f0f2f7; border: 1px solid #303646;"
            "  border-radius: 4px; padding: 5px 8px; font-family: Consolas, monospace; font-size: 10pt;"
            "}"
            "QLineEdit:focus { border: 1px solid #5884d6; }"
        )

    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()

        # Ctrl+C with no text selected triggers terminal process interrupt / stop
        if key == Qt.Key.Key_C and (modifiers & Qt.KeyboardModifier.ControlModifier):
            if not self.hasSelectedText():
                parent = self.parent()
                while parent and not hasattr(parent, "stop_process"):
                    parent = parent.parent()
                if parent and hasattr(parent, "stop_process"):
                    parent.stop_process()
                    return

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            text = self.text().strip()
            if text:
                if not self.history or self.history[-1] != text:
                    self.history.append(text)
                self.history_index = -1
                self._temp_input = ""
                self.clear()
                self.command_submitted.emit(text)
            return

        if key == Qt.Key.Key_Up:
            if not self.history:
                return
            if self.history_index == -1:
                self._temp_input = self.text()
            if self.history_index < len(self.history) - 1:
                self.history_index += 1
                self.setText(self.history[len(self.history) - 1 - self.history_index])
                self.setCursorPosition(len(self.text()))
            return

        if key == Qt.Key.Key_Down:
            if self.history_index > 0:
                self.history_index -= 1
                self.setText(self.history[len(self.history) - 1 - self.history_index])
                self.setCursorPosition(len(self.text()))
            elif self.history_index == 0:
                self.history_index = -1
                self.setText(self._temp_input)
                self.setCursorPosition(len(self.text()))
            return

        super().keyPressEvent(event)


class IntegratedTerminalWidget(QWidget):
    """
    Bottom-docked integrated terminal using QProcess and persistent PowerShell/CMD.
    """

    def __init__(self, initial_cwd=None, parent=None):
        super().__init__(parent)
        self.cwd = Path(initial_cwd).resolve() if initial_cwd else Path.cwd()
        self.shell_type = "PowerShell"
        self.process = None
        self._build_ui()
        self.start_shell()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 6)
        layout.setSpacing(4)

        # Header bar
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        self.shell_label = QLabel("Terminal (PowerShell)")
        self.shell_label.setStyleSheet("font-weight: 600; color: #8ab4f8; font-size: 9pt;")
        header_layout.addWidget(self.shell_label)

        self.cwd_label = QLabel()
        self.cwd_label.setStyleSheet("color: #7d8597; font-size: 9pt;")
        self._update_cwd_label()
        header_layout.addWidget(self.cwd_label, 1)

        self.new_btn = QPushButton("New")
        self.new_btn.setToolTip("Restart fresh terminal session in current directory")
        self.new_btn.setFixedHeight(24)
        self.new_btn.clicked.connect(self.restart_terminal)
        header_layout.addWidget(self.new_btn)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setToolTip("Clear terminal output")
        self.clear_btn.setFixedHeight(24)
        self.clear_btn.clicked.connect(self.clear_terminal)
        header_layout.addWidget(self.clear_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setToolTip("Stop running command / reset shell")
        self.stop_btn.setFixedHeight(24)
        self.stop_btn.setStyleSheet("QPushButton { color: #ff8585; } QPushButton:hover { background: #4a2828; }")
        self.stop_btn.clicked.connect(self.stop_process)
        header_layout.addWidget(self.stop_btn)

        layout.addLayout(header_layout)

        # Console Output Area
        self.output_area = QPlainTextEdit()
        self.output_area.setReadOnly(True)
        self.output_area.setFont(QFont("Consolas", 10))
        self.output_area.setMaximumBlockCount(5000)
        self.output_area.setStyleSheet(
            "QPlainTextEdit {"
            "  background: #111318; color: #d8dde8; border: 1px solid #282d3b;"
            "  border-radius: 4px; padding: 6px; selection-background-color: #385175;"
            "}"
        )
        layout.addWidget(self.output_area, 1)

        # Command Input Area
        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(6)

        self.prompt_label = QLabel("PS >")
        self.prompt_label.setStyleSheet("font-weight: bold; color: #64b5f6; font-family: Consolas; font-size: 10pt;")
        input_layout.addWidget(self.prompt_label)

        self.input_field = TerminalInputLineEdit()
        self.input_field.command_submitted.connect(self.execute_command)
        input_layout.addWidget(self.input_field, 1)

        layout.addLayout(input_layout)

    def _update_cwd_label(self):
        display = str(self.cwd)
        if len(display) > 55:
            display = "…" + display[-52:]
        self.cwd_label.setText(f"cwd: {display}")
        self.cwd_label.setToolTip(str(self.cwd))

    def _detect_shell(self):
        # Look for PowerShell first, then CMD
        ps = shutil.which("powershell.exe") or r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
        if os.path.exists(ps):
            return ps, ["-NoLogo", "-NoExit", "-ExecutionPolicy", "Bypass"], "PowerShell", "PS >"

        cmd = shutil.which("cmd.exe") or r"C:\Windows\System32\cmd.exe"
        return cmd, ["/k"], "CMD", "CMD >"

    def start_shell(self):
        self.shutdown()

        shell_path, shell_args, shell_name, prompt = self._detect_shell()
        self.shell_type = shell_name
        self.shell_label.setText(f"Terminal ({shell_name})")
        self.prompt_label.setText(prompt)

        self.process = QProcess(self)
        self.process.setWorkingDirectory(str(self.cwd))
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)

        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONUNBUFFERED", "1")
        env.insert("TERM", "dumb")
        self.process.setProcessEnvironment(env)

        self.process.readyReadStandardOutput.connect(self._handle_stdout)
        self.process.readyReadStandardError.connect(self._handle_stderr)
        self.process.finished.connect(self._handle_finished)
        self.process.errorOccurred.connect(self._handle_error)

        self.process.start(shell_path, shell_args)
        if not self.process.waitForStarted(2000):
            self._append_output(f"[Failed to start shell: {shell_path}]\n", is_error=True)
        else:
            self._append_output(f"--- OpenArise Terminal ({shell_name}) [{self.cwd}] ---\n")

    def _decode_bytes(self, raw_bytes: bytes) -> str:
        for encoding in ("utf-8", "cp1252", "cp437", "cp850", "latin-1"):
            try:
                return raw_bytes.decode(encoding)
            except UnicodeDecodeError:
                continue
        return raw_bytes.decode("utf-8", errors="replace")

    def _clean_ansi(self, text: str) -> str:
        return ANSI_ESCAPE_REGEX.sub("", text)

    def _append_output(self, text: str, is_error: bool = False):
        clean_text = self._clean_ansi(text)
        cursor = self.output_area.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(clean_text)
        self.output_area.setTextCursor(cursor)
        self.output_area.ensureCursorVisible()

    def _handle_stdout(self):
        if self.process:
            data = self.process.readAllStandardOutput().data()
            if data:
                text = self._decode_bytes(data)
                self._append_output(text)

    def _handle_stderr(self):
        if self.process:
            data = self.process.readAllStandardError().data()
            if data:
                text = self._decode_bytes(data)
                self._append_output(text, is_error=True)

    def _handle_finished(self, exit_code, exit_status):
        if not getattr(self, "_is_stopping", False):
            self._append_output(f"\n[Process exited with code {exit_code}]\n")

    def _handle_error(self, error):
        if not getattr(self, "_is_stopping", False):
            self._append_output(f"\n[Process error: {error}]\n", is_error=True)

    def execute_command(self, command: str):
        if not command:
            return
        if not self.process or self.process.state() != QProcess.ProcessState.Running:
            self.start_shell()

        self._append_output(f"{self.prompt_label.text()} {command}\n")
        encoded = (command + "\r\n").encode("utf-8")
        self.process.write(encoded)
        self.process.waitForBytesWritten(500)

    def clear_terminal(self):
        self.output_area.clear()

    def stop_process(self):
        if self.process and self.process.state() == QProcess.ProcessState.Running:
            self._is_stopping = True
            self._append_output("\n[Stopping process / resetting session…]\n")
            pid = self.process.processId()
            if sys.platform == "win32" and pid:
                try:
                    import subprocess
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, timeout=5)
                except Exception:
                    pass
            self.process.kill()
            self.process.waitForFinished(1000)
            self._is_stopping = False
            self.start_shell()

    def restart_terminal(self):
        self.clear_terminal()
        self.start_shell()

    def set_working_directory(self, path: Path):
        new_path = Path(path).resolve()
        self.cwd = new_path
        self._update_cwd_label()
        if self.process and self.process.state() == QProcess.ProcessState.Running:
            if self.shell_type == "PowerShell":
                self.execute_command(f'Set-Location -LiteralPath "{new_path}"')
            else:
                self.execute_command(f'cd /d "{new_path}"')

    def shutdown(self):
        if self.process:
            self._is_stopping = True
            pid = self.process.processId()
            if sys.platform == "win32" and pid and self.process.state() == QProcess.ProcessState.Running:
                try:
                    import subprocess
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, timeout=3)
                except Exception:
                    pass
            try:
                self.process.readyReadStandardOutput.disconnect()
            except Exception:
                pass
            try:
                self.process.readyReadStandardError.disconnect()
            except Exception:
                pass
            if self.process.state() == QProcess.ProcessState.Running:
                self.process.terminate()
                if not self.process.waitForFinished(800):
                    self.process.kill()
                    self.process.waitForFinished(500)
            self.process = None
            self._is_stopping = False

    def focus_input(self):
        self.input_field.setFocus()

