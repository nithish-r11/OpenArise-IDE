"""
Unified AI Container for OpenArise IDE.
Hosts both Chat Mode (conversational assistant) and Agent Mode (autonomous development)
with a clean top segmented switcher and complete backward compatibility with ChatPanel.
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QStackedWidget,
    QButtonGroup,
)

from core.context_manager import ContextManager
from core.ollama_client import OllamaClient
from ui.agent_panel import AgentPanel
from ui.chat_panel import ChatPanel


class ChatAgentContainer(QWidget):
    """
    Sidebar widget hosting both Chat Mode and Agent Mode.
    Forwards legacy ChatPanel signals and attributes to ensure zero regression.
    """

    mode_changed = pyqtSignal(str)  # 'chat' or 'agent'

    def __init__(
        self,
        client: OllamaClient,
        context_manager: Optional[ContextManager] = None,
        parent=None
    ):
        super().__init__(parent)
        self.client = client
        self.context_manager = context_manager

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Mode Switcher Bar
        switcher_box = QWidget()
        switcher_box.setStyleSheet("background-color: #161b22; border-bottom: 1px solid #30363d;")
        switcher_layout = QHBoxLayout(switcher_box)
        switcher_layout.setContentsMargins(8, 6, 8, 6)
        switcher_layout.setSpacing(6)

        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)

        self.btn_chat_mode = QPushButton("💬 Chat")
        self.btn_chat_mode.setCheckable(True)
        self.btn_chat_mode.setChecked(True)
        self.btn_chat_mode.setToolTip("Normal Conversational Coding Assistant")

        self.btn_agent_mode = QPushButton("🤖 Agent")
        self.btn_agent_mode.setCheckable(True)
        self.btn_agent_mode.setToolTip("Autonomous Project Development & Tool Execution (Ctrl+Shift+A)")

        mode_btn_style = """
            QPushButton {
                background-color: #21262d;
                color: #8b949e;
                border: 1px solid #30363d;
                border-radius: 4px;
                padding: 4px 14px;
                font-weight: 500;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #30363d;
                color: #c9d1d9;
            }
            QPushButton:checked {
                background-color: #1f6feb;
                border-color: #388bfd;
                color: #ffffff;
                font-weight: bold;
            }
        """
        self.btn_chat_mode.setStyleSheet(mode_btn_style)
        self.btn_agent_mode.setStyleSheet(mode_btn_style)

        self.btn_group.addButton(self.btn_chat_mode, 0)
        self.btn_group.addButton(self.btn_agent_mode, 1)

        self.btn_chat_mode.clicked.connect(lambda: self.set_mode("chat"))
        self.btn_agent_mode.clicked.connect(lambda: self.set_mode("agent"))

        switcher_layout.addWidget(self.btn_chat_mode, 1)
        switcher_layout.addWidget(self.btn_agent_mode, 1)
        layout.addWidget(switcher_box)

        # Stacked Widget for Chat vs Agent
        self.stack = QStackedWidget()
        self.chat_panel = ChatPanel(parent=self)
        self.agent_panel = AgentPanel(client=self.client, context_manager=self.context_manager, parent=self)

        self.stack.addWidget(self.chat_panel)   # Index 0
        self.stack.addWidget(self.agent_panel)  # Index 1
        layout.addWidget(self.stack, 1)

    def set_mode(self, mode: str):
        mode_lower = mode.lower()
        if mode_lower == "agent":
            self.stack.setCurrentIndex(1)
            self.btn_agent_mode.setChecked(True)
            self.agent_panel.task_input.setFocus()
            self.mode_changed.emit("agent")
        else:
            self.stack.setCurrentIndex(0)
            self.btn_chat_mode.setChecked(True)
            self.chat_panel.input.setFocus()
            self.mode_changed.emit("chat")

    def current_mode(self) -> str:
        return "agent" if self.stack.currentIndex() == 1 else "chat"

    def set_project_root(self, root: Optional[Path]):
        self.agent_panel.set_project_root(root)

    def set_models(self, models: list[str]):
        self.chat_panel.set_models(models)
        self.agent_panel.set_models(models)

    # --- Backward-Compatibility Proxies for ChatPanel ---

    @property
    def send_requested(self):
        return self.chat_panel.send_requested

    @property
    def inline_requested(self):
        return self.chat_panel.inline_requested

    @property
    def insert_code_requested(self):
        return self.chat_panel.insert_code_requested

    @property
    def input(self):
        return self.chat_panel.input

    @property
    def output(self):
        return self.chat_panel.output

    @property
    def refresh_button(self):
        return self.chat_panel.refresh_button

    def current_model(self) -> str:
        if self.current_mode() == "agent":
            return self.agent_panel.current_model() or self.chat_panel.current_model()
        return self.chat_panel.current_model()

    def send_message(self):
        self.chat_panel.send_message()

    def request_inline(self):
        self.chat_panel.request_inline()

    def append_user(self, text: str):
        self.chat_panel.append_user(text)

    def begin_response(self):
        self.chat_panel.begin_response()

    def append_token(self, token: str):
        self.chat_panel.append_token(token)

    def finish_response(self):
        self.chat_panel.finish_response()

    def show_error(self, message: str):
        self.chat_panel.show_error(message)

