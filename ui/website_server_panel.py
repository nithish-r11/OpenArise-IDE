"""
OpenArise IDE - Website Server Bottom Dock Tab Panel
Provides controls for running, stopping, and restarting the local development server,
displaying server status, URL copy, browser preview, and real-time logs.
"""

from __future__ import annotations
import webbrowser
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QTextCursor
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QFrame,
    QApplication,
)

from core.website_server import WebsiteServerManager, WebsiteServerState


class WebsiteServerPanel(QWidget):
    """
    Bottom dock tab displaying website development server status, controls, and logs.
    """
    run_requested = pyqtSignal()
    fix_errors_requested = pyqtSignal(str)

    def __init__(self, server_manager: WebsiteServerManager, parent=None):
        super().__init__(parent)
        self.server_manager = server_manager
        self.project_dir: Optional[Path] = None

        self._build_ui()
        self._connect_signals()
        self._update_ui_state(self.server_manager.state.value)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # -------------------------------------------------------------
        # Control & Status Header Bar
        # -------------------------------------------------------------
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        # Status Label / Badge
        self.status_badge = QLabel("STOPPED")
        self.status_badge.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_badge.setFixedHeight(26)
        self.status_badge.setMinimumWidth(80)
        self.status_badge.setStyleSheet(
            "background-color: #33333d; color: #a0a0b0; border-radius: 4px; padding: 2px 8px;"
        )
        top_bar.addWidget(self.status_badge)

        # URL Label
        self.url_label = QLabel("No server running")
        self.url_label.setFont(QFont("Consolas", 10))
        self.url_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.url_label.setStyleSheet("color: #8ab4f8; padding: 2px 6px;")
        top_bar.addWidget(self.url_label)

        # Action Buttons
        self.copy_url_btn = QPushButton("Copy URL")
        self.copy_url_btn.setToolTip("Copy local server URL to clipboard")
        self.copy_url_btn.clicked.connect(self._copy_url)
        self.copy_url_btn.setEnabled(False)
        top_bar.addWidget(self.copy_url_btn)

        self.open_browser_btn = QPushButton("Open in Browser")
        self.open_browser_btn.setToolTip("Open website in default web browser")
        self.open_browser_btn.setStyleSheet("font-weight: bold;")
        self.open_browser_btn.clicked.connect(self._open_browser)
        self.open_browser_btn.setEnabled(False)
        top_bar.addWidget(self.open_browser_btn)

        # Separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        sep.setStyleSheet("color: #33333d;")
        top_bar.addWidget(sep)

        self.run_btn = QPushButton("Run Website")
        self.run_btn.setToolTip("Start local development server (Ctrl+F5)")
        self.run_btn.clicked.connect(lambda: self.run_requested.emit())
        top_bar.addWidget(self.run_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setToolTip("Stop local development server")
        self.stop_btn.clicked.connect(self.server_manager.stop)
        self.stop_btn.setEnabled(False)
        top_bar.addWidget(self.stop_btn)

        self.restart_btn = QPushButton("Restart")
        self.restart_btn.setToolTip("Restart development server")
        self.restart_btn.clicked.connect(self.server_manager.restart)
        self.restart_btn.setEnabled(False)
        top_bar.addWidget(self.restart_btn)

        self.clear_btn = QPushButton("Clear Logs")
        self.clear_btn.setToolTip("Clear log console")
        self.clear_btn.clicked.connect(self._clear_logs)
        top_bar.addWidget(self.clear_btn)

        self.fix_ai_btn = QPushButton("Fix with AI")
        self.fix_ai_btn.setToolTip("Ask Ollama AI to diagnose and fix server error")
        self.fix_ai_btn.setStyleSheet(
            "background-color: #6366f1; color: #ffffff; font-weight: bold; border-radius: 4px; padding: 4px 10px;"
        )
        self.fix_ai_btn.clicked.connect(self._trigger_ai_fix)
        self.fix_ai_btn.hide()
        top_bar.addWidget(self.fix_ai_btn)

        top_bar.addStretch()
        root.addLayout(top_bar)

        # -------------------------------------------------------------
        # Log Output Console
        # -------------------------------------------------------------
        self.log_output = QTextBrowser()
        self.log_output.setFont(QFont("Consolas", 9))
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("""
            QTextBrowser {
                background-color: #121216;
                color: #c8c8d2;
                border: 1px solid #282832;
                border-radius: 4px;
                padding: 6px;
                font-family: Consolas, 'Courier New', monospace;
            }
        """)
        root.addWidget(self.log_output)

    def _connect_signals(self):
        self.server_manager.status_changed.connect(self._update_ui_state)
        self.server_manager.url_ready.connect(self._on_url_ready)
        self.server_manager.log_line.connect(self._append_log)
        self.server_manager.error_occurred.connect(self._on_error)

    def set_project(self, project_dir: Optional[Path]):
        """Sets the active project directory."""
        self.project_dir = Path(project_dir).resolve() if project_dir else None

    def _update_ui_state(self, state: str):
        if state == WebsiteServerState.RUNNING.value:
            self.status_badge.setText("RUNNING")
            self.status_badge.setStyleSheet(
                "background-color: #1e4620; color: #65d98b; border: 1px solid #2e7d32; border-radius: 4px; padding: 2px 8px;"
            )
            self.run_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.restart_btn.setEnabled(True)
            self.open_browser_btn.setEnabled(True)
            self.copy_url_btn.setEnabled(True)
            self.fix_ai_btn.hide()

        elif state == WebsiteServerState.STARTING.value:
            self.status_badge.setText("STARTING")
            self.status_badge.setStyleSheet(
                "background-color: #4a3800; color: #fdd835; border: 1px solid #7a5c00; border-radius: 4px; padding: 2px 8px;"
            )
            self.run_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.restart_btn.setEnabled(False)
            self.open_browser_btn.setEnabled(False)
            self.copy_url_btn.setEnabled(False)
            self.fix_ai_btn.hide()

        elif state == WebsiteServerState.ERROR.value:
            self.status_badge.setText("ERROR")
            self.status_badge.setStyleSheet(
                "background-color: #4a151b; color: #ff6b6b; border: 1px solid #7a222c; border-radius: 4px; padding: 2px 8px;"
            )
            self.run_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.restart_btn.setEnabled(True)
            self.open_browser_btn.setEnabled(False)
            self.copy_url_btn.setEnabled(False)
            self.fix_ai_btn.show()

        else:  # STOPPED
            self.status_badge.setText("STOPPED")
            self.status_badge.setStyleSheet(
                "background-color: #262630; color: #a0a0b0; border: 1px solid #383848; border-radius: 4px; padding: 2px 8px;"
            )
            self.url_label.setText("No server running")
            self.run_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.restart_btn.setEnabled(False)
            self.open_browser_btn.setEnabled(False)
            self.copy_url_btn.setEnabled(False)
            self.fix_ai_btn.hide()

    def _on_url_ready(self, url: str):
        self.url_label.setText(url)
        self.open_browser_btn.setEnabled(True)
        self.copy_url_btn.setEnabled(True)

    def _append_log(self, text: str):
        self.log_output.append(text)
        cursor = self.log_output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_output.setTextCursor(cursor)

    def _clear_logs(self):
        self.server_manager.clear_logs()
        self.log_output.clear()

    def _copy_url(self):
        url = self.server_manager.current_url
        if url:
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(url)
                self.copy_url_btn.setText("Copied!")
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(1500, lambda: self.copy_url_btn.setText("Copy URL"))

    def _open_browser(self):
        url = self.server_manager.current_url
        if url:
            try:
                webbrowser.open(url)
                self.server_manager._emit_log(f"Opened URL in system browser: {url}")
            except Exception as exc:
                self.server_manager._emit_log(f"[ERROR] Could not open browser: {exc}")

    def _on_error(self, err: str):
        self.fix_ai_btn.show()

    def _trigger_ai_fix(self):
        logs = "\n".join(self.server_manager.get_logs()[-30:])
        self.fix_errors_requested.emit(logs)

