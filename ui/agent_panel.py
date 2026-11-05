"""
AI Agent Panel UI for OpenArise IDE.
Provides project task execution, live plan visualization, interactive approval cards
for plans, terminal commands, and file diffs, execution logs, and rollback controls.
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QTextCursor
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QPushButton,
    QComboBox,
    QProgressBar,
    QTreeWidget,
    QTreeWidgetItem,
    QTextBrowser,
    QFrame,
    QSplitter,
    QMessageBox,
    QSizePolicy,
    QHeaderView,
)

from core.agent_models import (
    AgentJournal,
    AgentPlan,
    AgentPlanStep,
    AgentTaskState,
    AgentToolCall,
    FileChangeRecord,
    StepStatus,
)
from core.agent_orchestrator import AgentWorker
from core.context_manager import ContextManager
from core.ollama_client import OllamaClient
from ui.agent_diff_dialog import AgentDiffDialog


class AgentPanel(QWidget):
    """
    Dedicated AI Agent panel supporting autonomous multi-step coding,
    plan verification, approval gates, diff reviews, and transactional rollback.
    """

    task_started = pyqtSignal(str)
    task_finished = pyqtSignal()

    def __init__(
        self,
        client: OllamaClient,
        context_manager: Optional[ContextManager] = None,
        parent=None
    ):
        super().__init__(parent)
        self.client = client
        self.context_manager = context_manager
        self.project_root: Optional[Path] = None
        self.worker: Optional[AgentWorker] = None
        self.last_journal: Optional[AgentJournal] = None

        self._init_ui()

    def set_project_root(self, root: Optional[Path]):
        self.project_root = Path(root).resolve() if root else None
        if self.project_root:
            self.root_lbl.setText(f"Project: {self.project_root.name}")
            self.root_lbl.setToolTip(str(self.project_root))
        else:
            self.root_lbl.setText("No project folder open")
            self.root_lbl.setToolTip("")

    def set_models(self, models: list[str]):
        self.model_combo.clear()
        preferred = []
        for m in models:
            self.model_combo.addItem(m)
            if any(name in m.lower() for name in ("qwen2.5-coder", "deepseek-coder", "codellama")):
                preferred.append(m)
        if preferred:
            self.model_combo.setCurrentText(preferred[0])

    def current_model(self) -> str:
        return self.model_combo.currentText().strip()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Header Bar
        header = QHBoxLayout()
        title_lbl = QLabel("🤖 OpenArise Agent")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #58a6ff;")
        header.addWidget(title_lbl)
        header.addStretch()

        self.root_lbl = QLabel("No project folder open")
        self.root_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        header.addWidget(self.root_lbl)
        layout.addLayout(header)

        # Model Selector Row
        model_row = QHBoxLayout()
        model_lbl = QLabel("Model:")
        model_lbl.setStyleSheet("color: #c9d1d9; font-size: 12px;")
        self.model_combo = QComboBox()
        self.model_combo.setStyleSheet("""
            QComboBox {
                background-color: #21262d;
                border: 1px solid #30363d;
                border-radius: 4px;
                padding: 4px 8px;
                color: #c9d1d9;
                font-size: 12px;
            }
        """)
        model_row.addWidget(model_lbl)
        model_row.addWidget(self.model_combo, 1)
        layout.addLayout(model_row)

        # Task Input Box (stable fixed height to avoid vertical jumping)
        self.task_input = QTextEdit()
        self.task_input.setPlaceholderText("Describe the autonomous coding task (e.g. 'Add JWT authentication with login/register routes and tests')...")
        self.task_input.setFixedHeight(75)
        self.task_input.setStyleSheet("""
            QTextEdit {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 8px;
                color: #e6edf3;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
            }
            QTextEdit:focus {
                border-color: #58a6ff;
            }
        """)
        layout.addWidget(self.task_input)

        # Action Buttons Row
        action_row = QHBoxLayout()
        self.btn_start = QPushButton("▶ Start Agent Task")
        self.btn_start.setStyleSheet("""
            QPushButton {
                background-color: #238636;
                color: #ffffff;
                font-weight: bold;
                border: 1px solid #2ea043;
                border-radius: 4px;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background-color: #2ea043;
            }
            QPushButton:disabled {
                background-color: #21262d;
                color: #8b949e;
                border-color: #30363d;
            }
        """)
        self.btn_start.clicked.connect(self.start_task)

        self.btn_cancel = QPushButton("⏹ Cancel")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #da3633;
                color: #ffffff;
                border: 1px solid #f85149;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #f85149;
            }
            QPushButton:disabled {
                background-color: #21262d;
                color: #8b949e;
                border-color: #30363d;
            }
        """)
        self.btn_cancel.clicked.connect(self.cancel_task)

        self.btn_rollback = QPushButton("↺ Rollback")
        self.btn_rollback.setEnabled(False)
        self.btn_rollback.setToolTip("Rollback all modifications made during the last agent task")
        self.btn_rollback.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                color: #e6edf3;
                border: 1px solid #30363d;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #30363d;
            }
            QPushButton:disabled {
                color: #484f58;
            }
        """)
        self.btn_rollback.clicked.connect(self.rollback_last_task)

        action_row.addWidget(self.btn_start)
        action_row.addWidget(self.btn_cancel)
        action_row.addWidget(self.btn_rollback)
        layout.addLayout(action_row)

        # Progress Bar & Status Line (Permanently retain size when hidden to eliminate layout shifting)
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 0)
        sp = self.progress_bar.sizePolicy()
        sp.setRetainSizeWhenHidden(True)
        self.progress_bar.setSizePolicy(sp)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        self.status_lbl = QLabel("Ready")
        self.status_lbl.setFixedHeight(18)
        self.status_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.status_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        layout.addWidget(self.status_lbl)
        self._raw_status_text = "Ready"

        # Interactive Approval Card (Dynamic, compact fixed height to prevent compressing the plan/log views)
        self.approval_card = QFrame()
        self.approval_card.setFixedHeight(82)
        self.approval_card.setStyleSheet("""
            QFrame {
                background-color: #1f242c;
                border: 1px solid #e3b341;
                border-radius: 6px;
                padding: 6px 8px;
            }
        """)
        self.approval_card_layout = QVBoxLayout(self.approval_card)
        self.approval_card_layout.setContentsMargins(6, 4, 6, 4)
        self.approval_card_layout.setSpacing(4)

        self.approval_title = QLabel("Approval Required")
        self.approval_title.setStyleSheet("font-weight: bold; color: #f2cc60; font-size: 12px;")
        self.approval_desc = QLabel("Action details...")
        self.approval_desc.setStyleSheet("color: #e6edf3; font-size: 11px;")
        self.approval_desc.setWordWrap(True)
        self.approval_desc.setFixedHeight(28)

        self.approval_btn_row = QHBoxLayout()
        self.approval_btn_row.setSpacing(8)
        self.btn_approve = QPushButton("Approve")
        self.btn_approve.setStyleSheet("background-color: #238636; color: white; padding: 3px 12px; border-radius: 4px; font-weight: bold;")
        self.btn_reject = QPushButton("Reject")
        self.btn_reject.setStyleSheet("background-color: #da3633; color: white; padding: 3px 12px; border-radius: 4px;")
        self.approval_btn_row.addWidget(self.btn_approve)
        self.approval_btn_row.addWidget(self.btn_reject)

        self.approval_card_layout.addWidget(self.approval_title)
        self.approval_card_layout.addWidget(self.approval_desc)
        self.approval_card_layout.addLayout(self.approval_btn_row)
        self.approval_card.hide()
        layout.addWidget(self.approval_card)

        # Plan & Log Splitter (Configured with non-collapsible children and locked plan stretch to guarantee stable table heights)
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)

        # Plan Tree Widget
        plan_box = QWidget()
        plan_box.setMinimumHeight(120)
        plan_layout = QVBoxLayout(plan_box)
        plan_layout.setContentsMargins(0, 0, 0, 0)
        plan_layout.setSpacing(4)
        plan_lbl = QLabel("Development Plan")
        plan_lbl.setStyleSheet("font-size: 12px; font-weight: bold; color: #c9d1d9;")
        plan_layout.addWidget(plan_lbl)

        self.plan_tree = QTreeWidget()
        self.plan_tree.setHeaderLabels(["Step", "Status", "Details"])
        self.plan_tree.setColumnWidth(0, 160)
        self.plan_tree.setColumnWidth(1, 90)
        self.plan_tree.header().setStretchLastSection(True)
        self.plan_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.plan_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.plan_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.plan_tree.setUniformRowHeights(True)
        self.plan_tree.setMinimumHeight(110)
        self.plan_tree.setStyleSheet("""
            QTreeWidget {
                background-color: #0d1117;
                border: 1px solid #30363d;
                border-radius: 4px;
                color: #c9d1d9;
                font-size: 12px;
            }
            QTreeWidget::item {
                padding: 4px;
            }
        """)
        plan_layout.addWidget(self.plan_tree)
        splitter.addWidget(plan_box)

        # Activity Log Browser
        log_box = QWidget()
        log_box.setMinimumHeight(150)
        log_layout = QVBoxLayout(log_box)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.setSpacing(4)
        log_lbl = QLabel("Activity Timeline & Findings")
        log_lbl.setStyleSheet("font-size: 12px; font-weight: bold; color: #c9d1d9;")
        log_layout.addWidget(log_lbl)

        self.log_browser = QTextBrowser()
        self.log_browser.setMinimumHeight(140)
        self.log_browser.document().setDocumentMargin(4)
        self.log_browser.setStyleSheet("""
            QTextBrowser {
                background-color: #0d1117;
                border: 1px solid #30363d;
                border-radius: 4px;
                color: #8b949e;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                padding: 6px;
            }
        """)
        log_layout.addWidget(self.log_browser)
        splitter.addWidget(log_box)

        # Stretch factors: Plan box stays stable (0), Activity Timeline takes stretch (1)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([140, 260])
        self.splitter = splitter
        layout.addWidget(splitter, 1)

    def _set_status(self, text: str):
        """Sets the status text with tooltip and updates horizontal elision smoothly."""
        self._raw_status_text = text
        self.status_lbl.setToolTip(text)
        self._update_elided_status()

    def _update_elided_status(self):
        text = getattr(self, "_raw_status_text", "")
        if not text:
            return
        fm = self.status_lbl.fontMetrics()
        available_width = max(50, self.status_lbl.width() - 4)
        elided = fm.elidedText(text, Qt.TextElideMode.ElideRight, available_width)
        self.status_lbl.setText(elided)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_elided_status()

    # --- Task Execution Lifecycle ---

    def start_task(self):
        prompt = self.task_input.toPlainText().strip()
        if not prompt:
            QMessageBox.information(self, "OpenArise Agent", "Please enter a development task description.")
            return
        if not self.project_root:
            QMessageBox.information(self, "OpenArise Agent", "Please open a project folder first before running agent tasks.")
            return

        model = self.current_model()
        if not model:
            QMessageBox.warning(self, "OpenArise Agent", "No model selected. Please pull or select an Ollama model.")
            return

        # Save active task description, clear input field, and reset UI
        self.active_task_prompt = prompt
        self.task_input.clear()
        self.plan_tree.clear()
        self.log_browser.clear()
        self._append_log("info", f"<b>Task:</b> {prompt}")
        self.approval_card.hide()
        self.progress_bar.show()
        self.btn_start.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.btn_rollback.setEnabled(False)
        self._set_status("Planning development steps...")

        # Create worker
        self.worker = AgentWorker(
            client=self.client,
            model=model,
            project_root=self.project_root,
            user_prompt=prompt,
            context_manager=self.context_manager,
            parent=self
        )

        # Connect signals
        self.worker.state_changed.connect(self._on_state_changed)
        self.worker.log_emitted.connect(self._append_log)
        self.worker.preflight_warning.connect(self._on_preflight_warning)
        self.worker.plan_ready.connect(self._on_plan_ready)
        self.worker.step_started.connect(self._on_step_started)
        self.worker.step_finished.connect(self._on_step_finished)
        self.worker.tool_requested.connect(self._on_tool_approval_needed)
        self.worker.tool_finished.connect(self._on_tool_finished)
        self.worker.diff_ready.connect(self._on_diff_approval_needed)
        self.worker.task_completed.connect(self._on_task_completed)
        self.worker.task_failed.connect(self._on_task_failed)

        self.last_journal = self.worker.journal
        self.worker.start()
        self.task_started.emit(prompt)

    def cancel_task(self):
        if self.worker and self.worker.isRunning():
            self._set_status("Cancelling task...")
            self.worker.cancel()
            self.worker.wait(2000)
        self.btn_cancel.setEnabled(False)
        self.btn_start.setEnabled(True)
        self.progress_bar.hide()
        self.approval_card.hide()
        self._set_status("Task cancelled.")

    def rollback_last_task(self):
        if not self.last_journal:
            QMessageBox.information(self, "Rollback", "No recorded changes to roll back.")
            return

        confirm = QMessageBox.question(
            self,
            "Confirm Rollback",
            f"Are you sure you want to rollback all modifications from task '{self.last_journal.task_id}'?\n"
            "This will restore original file contents and delete newly created files.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            count, files = self.last_journal.rollback()
            self._append_log("warning", f"Rolled back {count} file(s): {', '.join(files)}")
            QMessageBox.information(self, "Rollback Complete", f"Successfully rolled back {count} file(s).")
            self.btn_rollback.setEnabled(False)

    # --- Signal Handlers ---

    def _on_state_changed(self, state_str: str):
        self._set_status(f"Status: {state_str.replace('_', ' ').title()}")

    def _append_log(self, level: str, msg: str):
        color_map = {
            "info": "#8b949e",
            "warning": "#d29922",
            "error": "#f85149",
            "success": "#3fb950"
        }
        color = color_map.get(level, "#c9d1d9")
        html_snippet = f'<span style="color:{color}">• {msg}</span>'

        sb = self.log_browser.verticalScrollBar()
        # User is viewing latest entries if scrollbar is within 20px of bottom
        was_at_bottom = sb.value() >= (sb.maximum() - 20)
        saved_val = sb.value()

        # Append using text cursor without stealing focus or forcing parent layout recalculations
        cursor = self.log_browser.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        if not self.log_browser.document().isEmpty():
            cursor.insertBlock()
        cursor.insertHtml(html_snippet)

        # Auto-scroll only when user was already at bottom; preserve scroll position when viewing older logs
        if was_at_bottom:
            sb.setValue(sb.maximum())
        else:
            sb.setValue(saved_val)

    def _on_preflight_warning(self, warning: str):
        self._append_log("warning", warning)

    def _on_plan_ready(self, plan: AgentPlan):
        self.plan_tree.clear()
        for step in plan.steps:
            item = QTreeWidgetItem([
                f"{step.step_number}. {step.description}",
                step.status.upper(),
                step.details
            ])
            item.setForeground(1, QColor("#8b949e"))
            self.plan_tree.addTopLevelItem(item)

        # Show Plan Approval Card
        self.approval_title.setText("Approve Development Plan")
        self.approval_desc.setText(
            f"The agent designed a {len(plan.steps)}-step plan. "
            "Please review the steps above and approve proceeding."
        )
        try:
            self.btn_approve.clicked.disconnect()
            self.btn_reject.clicked.disconnect()
        except TypeError:
            pass
        self.btn_approve.clicked.connect(lambda: self._handle_plan_decision(True))
        self.btn_reject.clicked.connect(lambda: self._handle_plan_decision(False))
        self.approval_card.show()

    def _handle_plan_decision(self, approved: bool):
        self.approval_card.hide()
        if self.worker:
            self.worker.approve_plan(approved)
        if not approved:
            self._set_status("Plan rejected by user.")
            self.btn_start.setEnabled(True)
            self.btn_cancel.setEnabled(False)
            self.progress_bar.hide()

    def _on_step_started(self, step_number: int, description: str):
        self._set_status(f"Running Step {step_number}: {description}")
        for i in range(self.plan_tree.topLevelItemCount()):
            item = self.plan_tree.topLevelItem(i)
            if item.text(0).startswith(f"{step_number}."):
                item.setText(1, "RUNNING")
                item.setForeground(1, QColor("#e3b341"))

    def _on_step_finished(self, step_number: int, status: str, summary: str):
        for i in range(self.plan_tree.topLevelItemCount()):
            item = self.plan_tree.topLevelItem(i)
            if item.text(0).startswith(f"{step_number}."):
                item.setText(1, status.upper())
                item.setText(2, summary)
                item.setForeground(1, QColor("#3fb950" if status == "completed" else "#f85149"))

    def _on_tool_approval_needed(self, tool_call: AgentToolCall):
        self.approval_title.setText("Tool Execution Approval Required")
        cmd = tool_call.args.get("command", "")
        self.approval_desc.setText(
            f"Tool: '{tool_call.name}'\n"
            f"Command: {cmd or tool_call.args}\n\n"
            "This command will execute directly on your local system with project permissions."
        )
        try:
            self.btn_approve.clicked.disconnect()
            self.btn_reject.clicked.disconnect()
        except TypeError:
            pass
        self.btn_approve.clicked.connect(lambda: self._handle_tool_decision(True))
        self.btn_reject.clicked.connect(lambda: self._handle_tool_decision(False))
        self.approval_card.show()

    def _handle_tool_decision(self, approved: bool):
        self.approval_card.hide()
        if self.worker:
            self.worker.approve_tool(approved)

    def _on_tool_finished(self, tool_call: AgentToolCall):
        pass

    def _on_diff_approval_needed(self, records: list[FileChangeRecord]):
        self._set_status("Awaiting diff review...")
        dlg = AgentDiffDialog(records, parent=self)
        res = dlg.exec()
        decisions = dlg.get_decisions()
        if self.worker:
            self.worker.submit_diff_decisions(decisions)

    def _on_task_completed(self, summary: str, suggested_commit: str):
        self._set_status("Task completed successfully!")
        self.progress_bar.hide()
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.btn_rollback.setEnabled(True)
        self.task_input.clear()
        formatted_summary = summary.replace("\n", "<br>")
        self._append_log("success", f"<b>TASK SUMMARY:</b><br>{formatted_summary}")
        if suggested_commit:
            self._append_log("info", f"<b>Suggested Commit:</b> <code>{suggested_commit}</code>")
        self.task_finished.emit()

    def _on_task_failed(self, error: str):
        self._set_status("Task failed.")
        self.progress_bar.hide()
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.btn_rollback.setEnabled(bool(self.last_journal and self.last_journal.records))
        self.approval_card.hide()
        self.task_input.clear()
        self._append_log("error", f"Task error: {error}")
        self.task_finished.emit()

