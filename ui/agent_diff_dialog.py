"""
Multi-File Diff Review and Approval Dialog for OpenArise AI Agent Mode.
Allows users to inspect original vs proposed code side-by-side or unified,
review line additions/deletions, and accept or reject changes per-file or in bulk.
"""

from __future__ import annotations
import difflib
import html
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QListWidget,
    QListWidgetItem,
    QTextBrowser,
    QLabel,
    QPushButton,
    QCheckBox,
    QFrame,
    QWidget,
)

from core.agent_models import FileChangeRecord, FileChangeType, FileChangeStatus


class AgentDiffDialog(QDialog):
    """
    Modal dialog allowing users to review proposed agent file changes before
    they are applied to the project disk.
    """

    def __init__(self, records: list[FileChangeRecord], parent=None):
        super().__init__(parent)
        self.records = records
        self.decisions: dict[str, bool] = {r.rel_path: True for r in records}  # Default: all checked

        self.setWindowTitle("Review Agent File Modifications — OpenArise IDE")
        self.resize(1050, 680)
        self.setMinimumSize(850, 500)
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e24;
                color: #e0e0e0;
                font-family: 'Segoe UI', sans-serif;
            }
            QListWidget {
                background-color: #16161a;
                border: 1px solid #33333d;
                border-radius: 6px;
                padding: 4px;
                color: #e0e0e0;
            }
            QListWidget::item {
                padding: 8px 10px;
                border-radius: 4px;
                margin-bottom: 2px;
            }
            QListWidget::item:selected {
                background-color: #2a2d3d;
                color: #ffffff;
            }
            QListWidget::item:hover {
                background-color: #22232e;
            }
            QTextBrowser {
                background-color: #141418;
                border: 1px solid #33333d;
                border-radius: 6px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 13px;
                color: #d4d4d4;
                padding: 10px;
            }
            QPushButton {
                background-color: #2b2b36;
                color: #ffffff;
                border: 1px solid #3e3e4f;
                border-radius: 4px;
                padding: 6px 14px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #383847;
                border-color: #55556b;
            }
            QPushButton#applyBtn {
                background-color: #1f6feb;
                border-color: #388bfd;
                font-weight: bold;
            }
            QPushButton#applyBtn:hover {
                background-color: #388bfd;
            }
            QPushButton#rejectBtn {
                background-color: #442726;
                border-color: #f85149;
                color: #f85149;
            }
            QPushButton#rejectBtn:hover {
                background-color: #5a2e2d;
            }
            QCheckBox {
                color: #e0e0e0;
                font-size: 13px;
            }
        """)

        self._init_ui()
        if self.records:
            self.file_list.setCurrentRow(0)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        header = QVBoxLayout()
        title = QLabel("Proposed File Modifications Review")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffffff;")
        subtitle = QLabel(
            f"The AI Agent proposed changes across {len(self.records)} file(s). "
            "Inspect diffs below. Only files marked as accepted will be applied to disk."
        )
        subtitle.setStyleSheet("color: #8b949e; font-size: 13px;")
        header.addWidget(title)
        header.addWidget(subtitle)
        layout.addLayout(header)

        # Main Splitter: File List (Left) vs Diff View (Right)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left Container: File list & bulk controls
        left_box = QWidget()
        left_layout = QVBoxLayout(left_box)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        left_hdr = QHBoxLayout()
        left_lbl = QLabel("Changed Files")
        left_lbl.setStyleSheet("font-weight: bold; font-size: 14px; color: #c9d1d9;")
        left_hdr.addWidget(left_lbl)
        left_hdr.addStretch()

        btn_select_all = QPushButton("Accept All")
        btn_select_all.setFixedHeight(24)
        btn_select_all.setStyleSheet("padding: 2px 8px; font-size: 11px;")
        btn_select_all.clicked.connect(self._accept_all)

        btn_deselect_all = QPushButton("Reject All")
        btn_deselect_all.setFixedHeight(24)
        btn_deselect_all.setStyleSheet("padding: 2px 8px; font-size: 11px;")
        btn_deselect_all.clicked.connect(self._reject_all)

        left_hdr.addWidget(btn_select_all)
        left_hdr.addWidget(btn_deselect_all)
        left_layout.addLayout(left_hdr)

        self.file_list = QListWidget()
        for rec in self.records:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, rec)
            item.setText(f"✓  {rec.rel_path} [{rec.change_type.upper()}]")
            item.setForeground(QColor("#58a6ff" if rec.change_type == "modify" else "#3fb950"))
            self.file_list.addItem(item)

        self.file_list.currentRowChanged.connect(self._on_file_selected)
        left_layout.addWidget(self.file_list, 1)

        splitter.addWidget(left_box)

        # Right Container: Diff viewer
        right_box = QWidget()
        right_layout = QVBoxLayout(right_box)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        # Diff Header
        diff_hdr = QHBoxLayout()
        self.current_file_lbl = QLabel("Select a file to inspect diff")
        self.current_file_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #58a6ff;")
        self.file_stats_lbl = QLabel("")
        self.file_stats_lbl.setStyleSheet("font-size: 12px; color: #8b949e;")

        self.current_file_checkbox = QCheckBox("Accept changes for this file")
        self.current_file_checkbox.setChecked(True)
        self.current_file_checkbox.toggled.connect(self._on_current_toggle)

        diff_hdr.addWidget(self.current_file_lbl)
        diff_hdr.addWidget(self.file_stats_lbl)
        diff_hdr.addStretch()
        diff_hdr.addWidget(self.current_file_checkbox)
        right_layout.addLayout(diff_hdr)

        self.diff_viewer = QTextBrowser()
        self.diff_viewer.setReadOnly(True)
        right_layout.addWidget(self.diff_viewer, 1)

        splitter.addWidget(right_box)
        splitter.setSizes([320, 730])
        layout.addWidget(splitter, 1)

        # Bottom Bar: Summary & Action Buttons
        bottom_box = QHBoxLayout()
        self.summary_lbl = QLabel(f"Accepted: {len(self.records)} of {len(self.records)} files")
        self.summary_lbl.setStyleSheet("color: #8b949e; font-size: 13px; font-weight: bold;")
        bottom_box.addWidget(self.summary_lbl)
        bottom_box.addStretch()

        btn_cancel = QPushButton("Reject All & Cancel")
        btn_cancel.setObjectName("rejectBtn")
        btn_cancel.clicked.connect(self._on_cancel_clicked)
        bottom_box.addWidget(btn_cancel)

        btn_apply = QPushButton("Apply Accepted Changes")
        btn_apply.setObjectName("applyBtn")
        btn_apply.clicked.connect(self._on_apply_clicked)
        bottom_box.addWidget(btn_apply)

        layout.addLayout(bottom_box)

    # --- Actions ---

    def _accept_all(self):
        for rec in self.records:
            self.decisions[rec.rel_path] = True
        self._refresh_list_labels()
        self._update_current_checkbox()

    def _reject_all(self):
        for rec in self.records:
            self.decisions[rec.rel_path] = False
        self._refresh_list_labels()
        self._update_current_checkbox()

    def _on_file_selected(self, row: int):
        if row < 0 or row >= len(self.records):
            return
        rec = self.records[row]
        self.current_file_lbl.setText(rec.rel_path)
        self.file_stats_lbl.setText(f"(+{rec.additions_count} / -{rec.deletions_count})")
        self._update_current_checkbox()
        self._render_diff(rec)

    def _on_current_toggle(self, checked: bool):
        row = self.file_list.currentRow()
        if 0 <= row < len(self.records):
            rec = self.records[row]
            self.decisions[rec.rel_path] = checked
            self._refresh_list_labels()

    def _update_current_checkbox(self):
        row = self.file_list.currentRow()
        if 0 <= row < len(self.records):
            rec = self.records[row]
            self.current_file_checkbox.blockSignals(True)
            self.current_file_checkbox.setChecked(self.decisions.get(rec.rel_path, True))
            self.current_file_checkbox.blockSignals(False)

    def _refresh_list_labels(self):
        accepted_count = 0
        for i, rec in enumerate(self.records):
            accepted = self.decisions.get(rec.rel_path, True)
            if accepted:
                accepted_count += 1
            item = self.file_list.item(i)
            if item:
                prefix = "✓" if accepted else "✗"
                item.setText(f"{prefix}  {rec.rel_path} [{rec.change_type.upper()}]")
                item.setForeground(QColor("#3fb950" if accepted else "#f85149"))
        self.summary_lbl.setText(f"Accepted: {accepted_count} of {len(self.records)} files")

    def _render_diff(self, rec: FileChangeRecord):
        old_lines = (rec.old_content or "").splitlines(keepends=True)
        new_lines = (rec.new_content or "").splitlines(keepends=True)

        diff = list(difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{rec.rel_path}",
            tofile=f"b/{rec.rel_path}",
            n=3
        ))

        if not diff and rec.change_type == FileChangeType.CREATE.value:
            # If creating a new file, synthesize unified added lines
            diff = [f"--- /dev/null\n", f"+++ b/{rec.rel_path}\n", f"@@ -0,0 +1,{len(new_lines)} @@\n"]
            for l in new_lines:
                diff.append(f"+{l}")

        html_out = [
            """<style>
                body { background-color: #141418; color: #d4d4d4; font-family: Consolas, monospace; font-size: 13px; line-height: 1.4; }
                .hunk { color: #8b949e; background-color: #1b1f27; font-weight: bold; padding: 2px 4px; }
                .add { color: #3fb950; background-color: #142a1e; }
                .del { color: #f85149; background-color: #2e1619; }
                .header { color: #58a6ff; font-weight: bold; }
                .line { white-space: pre-wrap; margin: 0; padding: 1px 4px; }
            </style><body>"""
        ]

        for line in diff:
            escaped = html.escape(line.rstrip("\r\n"))
            if line.startswith("+++") or line.startswith("---"):
                html_out.append(f'<div class="line header">{escaped}</div>')
            elif line.startswith("@@"):
                html_out.append(f'<div class="line hunk">{escaped}</div>')
            elif line.startswith("+"):
                html_out.append(f'<div class="line add">{escaped}</div>')
            elif line.startswith("-"):
                html_out.append(f'<div class="line del">{escaped}</div>')
            else:
                html_out.append(f'<div class="line">{escaped}</div>')

        html_out.append("</body>")
        self.diff_viewer.setHtml("".join(html_out))

    def _on_apply_clicked(self):
        self.accept()

    def _on_cancel_clicked(self):
        # Mark all as rejected
        for rec in self.records:
            self.decisions[rec.rel_path] = False
        self.reject()

    def get_decisions(self) -> dict[str, bool]:
        """Returns mapping of relative path to accepted boolean flag."""
        return dict(self.decisions)

    def get_accepted_records(self) -> list[FileChangeRecord]:
        """Returns the list of FileChangeRecord items that the user accepted."""
        return [r for r in self.records if self.decisions.get(r.rel_path, False)]

