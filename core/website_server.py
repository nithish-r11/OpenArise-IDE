"""
OpenArise IDE - Local Website Development Server Manager
Manages asynchronous background development servers (Python http.server for HTML/CSS/JS
and Vite / Node dev servers for React) bound strictly to 127.0.0.1.
Enforces process isolation, strict port allocation, dependency approval gates,
and clean process-tree termination.
"""

from __future__ import annotations
import os
import re
import socket
import subprocess
import sys
import time
from enum import Enum
from pathlib import Path
from typing import Optional, Callable

from PyQt6.QtCore import QObject, QProcess, pyqtSignal, QTimer


class WebsiteServerState(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"


def is_port_available(port: int, host: str = "127.0.0.1") -> bool:
    """Checks whether a TCP port is currently free on the specified host."""
    # 1. First probe if any server is actively listening on this port
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.3)
            if sock.connect_ex((host, port)) == 0:
                return False
    except OSError:
        pass

    # 2. Test binding to ensure exclusive address availability (without SO_REUSEADDR on Windows)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((host, port))
            return True
    except OSError:
        return False


def find_available_port(start_port: int = 8000, host: str = "127.0.0.1", max_tries: int = 200) -> int:
    """Finds the next available port on the host, starting from start_port."""
    for port in range(start_port, start_port + max_tries):
        if is_port_available(port, host):
            return port
    raise RuntimeError(f"No available port found on {host} between {start_port} and {start_port + max_tries}")


class WebsiteServerManager(QObject):
    """
    Manages local web server lifecycle (HTML static or React+Vite).
    Runs asynchronously on QProcess without blocking the UI thread.
    """
    status_changed = pyqtSignal(str)       # Emits WebsiteServerState value
    url_ready = pyqtSignal(str)            # Emits e.g. "http://127.0.0.1:8000"
    log_line = pyqtSignal(str)             # Emits formatted server log lines
    error_occurred = pyqtSignal(str)       # Emits error descriptions
    port_selected = pyqtSignal(int)        # Emits allocated port number

    def __init__(self, parent_or_project: Any = None, project_dir: Optional[Path] = None, parent: Optional[QObject] = None):
        # Allow flexible initialization:
        # WebsiteServerManager(parent=self)
        # WebsiteServerManager(project_dir)
        # WebsiteServerManager(parent=self, project_dir=path)
        actual_parent = parent
        actual_project_dir = project_dir

        if isinstance(parent_or_project, (str, Path)):
            if actual_project_dir is None:
                actual_project_dir = Path(parent_or_project)
        elif isinstance(parent_or_project, QObject):
            if actual_parent is None:
                actual_parent = parent_or_project
        elif parent_or_project is not None and actual_project_dir is None:
            try:
                actual_project_dir = Path(parent_or_project)
            except Exception:
                pass

        super().__init__(actual_parent)
        self.state: WebsiteServerState = WebsiteServerState.STOPPED
        self.current_url: Optional[str] = None
        self.current_port: Optional[int] = None
        self.project_dir: Optional[Path] = actual_project_dir
        self.project_type: str = "html"
        self.process: Optional[QProcess] = None
        self.interpreter: str = sys.executable
        self.dependency_approval_handler: Optional[Callable[[str, str], bool]] = None
        self._startup_timer: Optional[QTimer] = None
        self._captured_logs: list[str] = []

    @property
    def url(self) -> Optional[str]:
        """Returns the currently active local server URL or None."""
        return self.current_url

    @property
    def port(self) -> Optional[int]:
        """Returns the currently allocated server port or None."""
        return self.current_port

    def set_interpreter(self, interpreter_path: str):
        """Sets the Python interpreter used for static HTTP servers."""
        if interpreter_path and Path(interpreter_path).exists():
            self.interpreter = str(Path(interpreter_path).resolve())

    def set_dependency_approval_handler(self, handler: Callable[[str, str], bool]):
        """Sets callback for requesting user approval before installing dependencies."""
        self.dependency_approval_handler = handler

    def detect_project_type(self, project_dir: Path) -> str:
        """Determines if the project is React+Vite or static HTML."""
        project_dir = Path(project_dir)
        pkg_json = project_dir / "package.json"
        if pkg_json.exists():
            return "react"
        return "html"

    def detect_package_manager(self, project_dir: Path) -> str:
        """Detects package manager from lockfiles or falls back to npm."""
        project_dir = Path(project_dir)
        if (project_dir / "pnpm-lock.yaml").exists():
            return "pnpm"
        if (project_dir / "yarn.lock").exists():
            return "yarn"
        return "npm"

    def is_running(self) -> bool:
        """Checks if server process is actively running."""
        return self.state in (WebsiteServerState.RUNNING, WebsiteServerState.STARTING) and (
            self.process is not None and self.process.state() == QProcess.ProcessState.Running
        )

    def get_logs(self) -> list[str]:
        """Returns captured log lines."""
        return list(self._captured_logs)

    def clear_logs(self):
        """Clears captured logs."""
        self._captured_logs.clear()

    def start(self, project_dir: Optional[Path] = None, port: Optional[int] = None) -> bool:
        """
        Starts the local development server for the given project directory.
        If project_dir is omitted, uses the project_dir configured during initialization.
        """
        target_dir = project_dir or self.project_dir
        if not target_dir:
            err_msg = "Cannot run server: no project directory specified."
            self._set_state(WebsiteServerState.ERROR)
            self.error_occurred.emit(err_msg)
            self._emit_log(f"[ERROR] {err_msg}")
            return False

        target_dir = Path(target_dir).resolve()
        if not target_dir.exists() or not target_dir.is_dir():
            err_msg = f"Cannot run server: directory does not exist ({target_dir})"
            self._set_state(WebsiteServerState.ERROR)
            self.error_occurred.emit(err_msg)
            self._emit_log(f"[ERROR] {err_msg}")
            return False

        if self.is_running():
            self.stop()

        self.project_dir = target_dir
        self.project_type = self.detect_project_type(target_dir)
        self.clear_logs()

        # Allocate port
        base_port = 8000 if self.project_type == "html" else 5173
        target_port = port if (port and is_port_available(port)) else find_available_port(base_port)
        self.current_port = target_port
        self.port_selected.emit(target_port)

        self._set_state(WebsiteServerState.STARTING)
        self._emit_log(f"--- Starting local website server ({self.project_type.upper()}) on port {target_port} ---")
        self._emit_log(f"Project directory: {target_dir}")

        # Check React dependencies
        if self.project_type == "react":
            node_modules = target_dir / "node_modules"
            if not node_modules.exists() or not any(node_modules.iterdir()):
                pm = self.detect_package_manager(target_dir)
                approved = False
                if self.dependency_approval_handler:
                    approved = self.dependency_approval_handler(
                        f"Install Dependencies ({pm})",
                        f"The React project at '{target_dir.name}' requires dependencies before starting.\n"
                        f"Run '{pm} install' now?"
                    )
                if not approved:
                    err = "Dependency installation was not approved. Cannot start React development server."
                    self._set_state(WebsiteServerState.ERROR)
                    self.error_occurred.emit(err)
                    self._emit_log(f"[ABORTED] {err}")
                    return False

                self._emit_log(f"Installing dependencies using '{pm} install'...")
                install_success = self._run_dependency_install(target_dir, pm)
                if not install_success:
                    err = f"Failed to install dependencies with '{pm} install'."
                    self._set_state(WebsiteServerState.ERROR)
                    self.error_occurred.emit(err)
                    return False

        # Launch process
        self.process = QProcess(self)
        self.process.setWorkingDirectory(str(target_dir))

        if self.project_type == "html":
            program = self.interpreter
            args = ["-m", "http.server", str(target_port), "--bind", "127.0.0.1"]
        else:
            pm = self.detect_package_manager(target_dir)
            # Use shell executable resolution for npm/pnpm on Windows
            program = pm + (".cmd" if sys.platform == "win32" and not pm.endswith(".cmd") else "")
            args = ["run", "dev", "--", "--port", str(target_port), "--host", "127.0.0.1"]

        self.process.readyReadStandardOutput.connect(self._handle_stdout)
        self.process.readyReadStandardError.connect(self._handle_stderr)
        self.process.finished.connect(self._handle_finished)
        self.process.errorOccurred.connect(self._handle_error_occurred)

        self._emit_log(f"Executing: {program} {' '.join(args)}")
        self.process.start(program, args)

        # Set fallback URL timer
        expected_url = f"http://127.0.0.1:{target_port}"
        self._startup_timer = QTimer(self)
        self._startup_timer.setSingleShot(True)
        self._startup_timer.timeout.connect(lambda: self._confirm_started(expected_url))
        self._startup_timer.start(1500)

        return True

    def _run_dependency_install(self, project_dir: Path, pm: str) -> bool:
        """Runs npm/pnpm install synchronously before starting Vite."""
        cmd = [pm + (".cmd" if sys.platform == "win32" else ""), "install"]
        try:
            self._emit_log(f"Running: {' '.join(cmd)} in {project_dir}")
            res = subprocess.run(
                cmd,
                cwd=str(project_dir),
                capture_output=True,
                text=True,
                timeout=180,
                check=False
            )
            if res.stdout:
                for line in res.stdout.splitlines():
                    self._emit_log(f"[{pm}] {line}")
            if res.stderr:
                for line in res.stderr.splitlines():
                    self._emit_log(f"[{pm} stderr] {line}")
            return res.returncode == 0
        except Exception as exc:
            self._emit_log(f"[ERROR] Failed executing dependency install: {exc}")
            return False

    def _confirm_started(self, expected_url: str):
        """Timer callback confirming server is running if process is healthy."""
        if self.process and self.process.state() == QProcess.ProcessState.Running:
            if self.state == WebsiteServerState.STARTING:
                self.current_url = expected_url
                self._set_state(WebsiteServerState.RUNNING)
                self.url_ready.emit(expected_url)
                self._emit_log(f"[SUCCESS] Website is live at: {expected_url}")

    def _handle_stdout(self):
        if not self.process:
            return
        data = self.process.readAllStandardOutput().data().decode("utf-8", errors="replace")
        for line in data.splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            self._emit_log(line_str)
            self._parse_server_output(line_str)

    def _handle_stderr(self):
        if not self.process:
            return
        data = self.process.readAllStandardError().data().decode("utf-8", errors="replace")
        for line in data.splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            # Note: Python's http.server outputs access logs to stderr by design
            self._emit_log(f"[SERVER] {line_str}")
            self._parse_server_output(line_str)

    def _parse_server_output(self, line: str):
        """Scans output line for server readiness and URL."""
        # Check standard http.server pattern
        m_http = re.search(r"Serving HTTP on (?:0\.0\.0\.0|127\.0\.0\.1) port (\d+)", line)
        if m_http:
            port = int(m_http.group(1))
            self.current_port = port
            url = f"http://127.0.0.1:{port}"
            self.current_url = url
            self._set_state(WebsiteServerState.RUNNING)
            self.url_ready.emit(url)
            return

        # Check Vite / Node pattern
        m_vite = re.search(r"(?:Local:\s+)?(http://(?:localhost|127\.0\.0\.1):(\d+))", line)
        if m_vite:
            port = int(m_vite.group(2))
            self.current_port = port
            url = f"http://127.0.0.1:{port}"
            self.current_url = url
            self._set_state(WebsiteServerState.RUNNING)
            self.url_ready.emit(url)
            return

        # Check error triggers
        if "Address already in use" in line or "EADDRINUSE" in line:
            self._set_state(WebsiteServerState.ERROR)
            self.error_occurred.emit(f"Port {self.current_port} is already in use by another process.")

    def _handle_finished(self, exit_code: int, exit_status: QProcess.ExitStatus):
        self._emit_log(f"--- Server process exited with code {exit_code} ({exit_status}) ---")
        if self._startup_timer:
            self._startup_timer.stop()

        if self.state == WebsiteServerState.STARTING or (exit_code != 0 and self.state != WebsiteServerState.STOPPED):
            self._set_state(WebsiteServerState.ERROR)
            self.error_occurred.emit(f"Server stopped unexpectedly with exit code {exit_code}.")
        else:
            self._set_state(WebsiteServerState.STOPPED)

    def _handle_error_occurred(self, err: QProcess.ProcessError):
        err_msg = f"Process error: {err}"
        self._emit_log(f"[ERROR] {err_msg}")
        if self.state != WebsiteServerState.STOPPED:
            self._set_state(WebsiteServerState.ERROR)
            self.error_occurred.emit(err_msg)

    def stop(self) -> bool:
        """
        Cleanly and thoroughly stops the running server process and its children.
        """
        if self._startup_timer:
            self._startup_timer.stop()

        self._set_state(WebsiteServerState.STOPPED)

        if self.process:
            pid = self.process.processId()
            self._emit_log("Stopping local development server...")
            try:
                self.process.finished.disconnect(self._handle_finished)
            except Exception:
                pass
            try:
                self.process.errorOccurred.disconnect(self._handle_error_occurred)
            except Exception:
                pass

            try:
                self.process.terminate()
            except Exception:
                pass

            # On Windows, enforce child process termination with taskkill
            if pid and sys.platform == "win32":
                try:
                    subprocess.run(
                        ["taskkill", "/PID", str(pid), "/T", "/F"],
                        capture_output=True,
                        check=False,
                        timeout=3
                    )
                except Exception:
                    pass

            try:
                if not self.process.waitForFinished(1500):
                    self.process.kill()
                    self.process.waitForFinished(1000)
            except Exception:
                pass

            self.process = None

        self.current_url = None
        self.current_port = None
        self._set_state(WebsiteServerState.STOPPED)
        self._emit_log("--- Server stopped cleanly ---")
        return True

    def restart(self) -> bool:
        """Restarts the development server using current project settings."""
        if not self.project_dir:
            return False
        p_dir = self.project_dir
        port = self.current_port
        self.stop()
        time.sleep(0.3)
        return self.start(p_dir, port)

    def _set_state(self, new_state: WebsiteServerState):
        if self.state != new_state:
            self.state = new_state
            self.status_changed.emit(new_state.value)

    def _emit_log(self, text: str):
        now = time.strftime("%H:%M:%S")
        formatted = f"[{now}] {text}"
        self._captured_logs.append(formatted)
        self.log_line.emit(formatted)
