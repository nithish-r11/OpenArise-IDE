"""
Visual Git Diff Viewer for OpenArise IDE.
Provides color-coded unified and side-by-side diff displays
with line numbers, hunk headers, and change metadata.
"""

from typing import Optional
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor, QTextCursor, QTextCharFormat
from PyQt6.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QSplitter,
    QPlainTextEdit,
)

from core.git_models import DiffFile
from core.git_service import GitService


class DiffViewerDialog(QDialog):
    """
    Dialog displaying formatted color-coded diffs for a file or commit.
    Read-only safe inspection: never alters disk contents.
    """

    def __init__(
        self,
        file_path: str,
        raw_diff: str,
        is_staged: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.file_path = file_path
        self.raw_diff = raw_diff
        self.is_staged = is_staged
        self.diff_data: DiffFile = GitService.parse_diff(raw_diff, file_path=file_path, is_staged=is_staged)

        staged_label = "Staged" if is_staged else "Unstaged"
        self.setWindowTitle(f"Diff: {file_path} ({staged_label}) — OpenArise IDE")
        self.resize(960, 680)
        self.setStyleSheet("background-color: #171920; color: #e6e8ef;")
        self._build_ui()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(8)

        # Header Bar: Filename, State, Stats
        header_bar = QHBoxLayout()
        header_bar.setSpacing(10)

        icon_lbl = QLabel("📄")
        icon_lbl.setStyleSheet("font-size: 14pt;")
        header_bar.addWidget(icon_lbl)

        title_lbl = QLabel(f"<b>{self.file_path}</b>")
        title_lbl.setStyleSheet("font-size: 11pt; color: #ffffff;")
        header_bar.addWidget(title_lbl)

        badge_text = "STAGED" if self.is_staged else "WORKING TREE (UNSTAGED)"
        badge_color = "#65d98b" if self.is_staged else "#e5c07b"
        badge_lbl = QLabel(badge_text)
        badge_lbl.setStyleSheet(
            f"background: #202636; color: {badge_color}; border: 1px solid {badge_color}44; "
            f"border-radius: 4px; padding: 2px 8px; font-weight: bold; font-size: 8.5pt;"
        )
        header_bar.addWidget(badge_lbl)

        # Count additions / deletions
        adds = sum(1 for line in self.diff_data.lines if line.line_type == "+")
        dels = sum(1 for line in self.diff_data.lines if line.line_type == "-")
        stats_lbl = QLabel(f"<span style='color:#7ee787;'>+{adds}</span>  <span style='color:#ff7b72;'>-{dels}</span>")
        stats_lbl.setStyleSheet("font-size: 10pt; font-weight: bold; margin-left: 8px;")
        header_bar.addWidget(stats_lbl)

        header_bar.addStretch(1)

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet("background: #2a3346; color: #e6e8ef; border-radius: 4px; padding: 5px 14px;")
        close_btn.clicked.connect(self.accept)
        header_bar.addWidget(close_btn)

        root_layout.addLayout(header_bar)

        # Diff View (HTML Rich Text for high performance syntax & line coloring)
        self.diff_browser = QTextBrowser()
        self.diff_browser.setReadOnly(True)
        self.diff_browser.setFont(QFont("Consolas", 10))
        self.diff_browser.setStyleSheet(
            "QTextBrowser { background-color: #13151b; border: 1px solid #282f40; border-radius: 6px; padding: 6px; }"
        )
        self._render_html_diff()
        root_layout.addWidget(self.diff_browser, 1)

    def _render_html_diff(self):
        if not self.diff_data.lines:
            if not self.raw_diff.strip():
                self.diff_browser.setHtml(
                    "<div style='color: #79869c; padding: 24px; text-align: center; font-size: 11pt;'>"
                    "No differences detected between working copy and repository index.</div>"
                )
            else:
                self.diff_browser.setPlainText(self.raw_diff)
            return

        html_parts = [
            "<style>",
            "body { font-family: Consolas, monospace; font-size: 9.5pt; line-height: 1.45; background: #13151b; margin: 0; }",
            "table { width: 100%; border-collapse: collapse; }",
            "td { padding: 1px 6px; white-space: pre-wrap; vertical-align: top; }",
            ".line-num { width: 44px; color: #5c6370; text-align: right; user-select: none; border-right: 1px solid #232734; padding-right: 8px; }",
            ".line-sign { width: 18px; text-align: center; user-select: none; }",
            ".add-row { background-color: rgba(46, 160, 67, 0.18); color: #85e89d; }",
            ".add-row .line-sign { color: #56d364; font-weight: bold; }",
            ".del-row { background-color: rgba(248, 81, 73, 0.18); color: #fdaeb7; }",
            ".del-row .line-sign { color: #f85149; font-weight: bold; }",
            ".hunk-row { background-color: rgba(56, 139, 253, 0.12); color: #79c0ff; font-weight: bold; }",
            ".hunk-num { color: #4384db; font-style: italic; }",
            ".ctx-row { color: #abb2bf; }",
            "</style>",
            "<table>",
        ]

        for line in self.diff_data.lines:
            c = line.content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            if line.line_type == "@":
                html_parts.append(
                    f"<tr class='hunk-row'><td class='line-num hunk-num'>…</td>"
                    f"<td class='line-num hunk-num'>…</td><td class='line-sign'>@</td><td>{c}</td></tr>"
                )
            elif line.line_type == "+":
                new_str = str(line.new_line_num) if line.new_line_num is not None else ""
                html_parts.append(
                    f"<tr class='add-row'><td class='line-num'></td><td class='line-num'>{new_str}</td>"
                    f"<td class='line-sign'>+</td><td>{c}</td></tr>"
                )
            elif line.line_type == "-":
                old_str = str(line.old_line_num) if line.old_line_num is not None else ""
                html_parts.append(
                    f"<tr class='del-row'><td class='line-num'>{old_str}</td><td class='line-num'></td>"
                    f"<td class='line-sign'>-</td><td>{c}</td></tr>"
                )
            else:
                old_str = str(line.old_line_num) if line.old_line_num is not None else ""
                new_str = str(line.new_line_num) if line.new_line_num is not None else ""
                html_parts.append(
                    f"<tr class='ctx-row'><td class='line-num'>{old_str}</td><td class='line-num'>{new_str}</td>"
                    f"<td class='line-sign'> </td><td>{c}</td></tr>"
                )

        html_parts.append("</table>")
        self.diff_browser.setHtml("\n".join(html_parts))

