"""
Git History Viewer Dialog for OpenArise IDE.
Inspects commit logs, authors, timestamps, and per-commit diffs.
"""

from pathlib import Path
from typing import List, Optional
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QTextBrowser,
    QSplitter,
    QPushButton,
    QWidget,
)

from core.git_models import GitCommit
from core.git_service import GitService


class GitHistoryDialog(QDialog):
    """Dialog displaying commit log history with integrated commit diff viewer."""

    def __init__(self, repo_path: Path, parent=None):
        super().__init__(parent)
        self.repo_path = Path(repo_path).resolve()
        self.commits: List[GitCommit] = []

        self.setWindowTitle(f"Git History — {self.repo_path.name}")
        self.resize(1000, 650)
        self.setStyleSheet("background-color: #171920; color: #e6e8ef;")
        self._build_ui()
        self.load_history()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(8)

        # Header: search & close
        top_bar = QHBoxLayout()
        header_title = QLabel("📜 Git Commit History")
        header_title.setStyleSheet("font-size: 11pt; font-weight: bold; color: #ffffff;")
        top_bar.addWidget(header_title)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter commits by message or author…")
        self.search_input.setStyleSheet("background: #1b1e26; border: 1px solid #333d52; border-radius: 4px; padding: 4px 8px; color: #fff;")
        self.search_input.textChanged.connect(self._filter_commits)
        top_bar.addWidget(self.search_input, 1)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setStyleSheet("background: #2a3346; color: #8ab4f8; border-radius: 4px; padding: 4px 10px;")
        refresh_btn.clicked.connect(self.load_history)
        top_bar.addWidget(refresh_btn)

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet("background: #2a3346; color: #e6e8ef; border-radius: 4px; padding: 4px 10px;")
        close_btn.clicked.connect(self.accept)
        top_bar.addWidget(close_btn)

        root_layout.addLayout(top_bar)

        # Splitter: Commits List (Left) and Commit Details/Diff (Right)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.commits_list = QListWidget()
        self.commits_list.setStyleSheet(
            "QListWidget { background: #13151b; border: 1px solid #282f40; border-radius: 4px; outline: none; }"
            "QListWidget::item { padding: 8px; border-bottom: 1px solid #1f2430; }"
            "QListWidget::item:selected { background: #232c3d; }"
        )
        self.commits_list.itemClicked.connect(self._on_commit_selected)
        splitter.addWidget(self.commits_list)

        # Commit Details Pane
        details_widget = QWidget()
        details_layout = QVBoxLayout(details_widget)
        details_layout.setContentsMargins(6, 6, 6, 6)

        self.commit_header_lbl = QLabel("Select a commit to view details")
        self.commit_header_lbl.setStyleSheet("font-size: 10pt; font-weight: bold; color: #8ab4f8;")
        self.commit_header_lbl.setWordWrap(True)
        details_layout.addWidget(self.commit_header_lbl)

        self.commit_meta_lbl = QLabel("")
        self.commit_meta_lbl.setStyleSheet("font-size: 9pt; color: #79869c; margin-bottom: 4px;")
        details_layout.addWidget(self.commit_meta_lbl)

        self.diff_browser = QTextBrowser()
        self.diff_browser.setReadOnly(True)
        self.diff_browser.setStyleSheet("background: #13151b; border: 1px solid #282f40; border-radius: 4px; color: #d7dae0; font-family: Consolas, monospace; font-size: 9pt;")
        details_layout.addWidget(self.diff_browser, 1)

        splitter.addWidget(details_widget)
        splitter.setSizes([420, 560])

        root_layout.addWidget(splitter, 1)

    def load_history(self):
        ok, msg, commits = GitService.get_history(self.repo_path, max_count=100)
        self.commits = commits if ok else []
        self._populate_list(self.commits)

    def _filter_commits(self, query: str):
        q = query.strip().lower()
        if not q:
            self._populate_list(self.commits)
            return
        filtered = [
            c for c in self.commits
            if q in c.message.lower() or q in c.author_name.lower() or q in c.short_sha.lower()
        ]
        self._populate_list(filtered)

    def _populate_list(self, commit_list: List[GitCommit]):
        self.commits_list.clear()
        for c in commit_list:
            item = QListWidgetItem(self.commits_list)
            # Create a simple multi-line display
            text = f"[{c.short_sha}] {c.message}\n  {c.author_name} • {c.date_str}"
            item.setText(text)
            item.setData(Qt.ItemDataRole.UserRole, c)
            self.commits_list.addItem(item)

        if self.commits_list.count() > 0:
            self.commits_list.setCurrentRow(0)
            self._on_commit_selected(self.commits_list.item(0))

    def _on_commit_selected(self, item: QListWidgetItem):
        if not item:
            return
        commit: GitCommit = item.data(Qt.ItemDataRole.UserRole)
        self.commit_header_lbl.setText(f"Commit: {commit.sha}\n{commit.message}")
        self.commit_meta_lbl.setText(f"Author: {commit.author_name} <{commit.author_email}>  •  Date: {commit.date_str}")

        ok, raw_out, _ = GitService.get_commit_diff(self.repo_path, commit.sha)
        if ok and raw_out:
            self.diff_browser.setPlainText(raw_out)
        else:
            self.diff_browser.setPlainText("No diff available for this commit.")

