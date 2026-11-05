"""
Source Control Panel for OpenArise IDE.
Provides Git status, staging, unstaging, commit, push, pull, fetch,
branch management, diff viewing, and AI-assisted Git workflows.
"""

from pathlib import Path
from typing import List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QPlainTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QMenu,
    QMessageBox,
    QProgressBar,
    QInputDialog,
    QFrame,
)

from core.git_models import (
    GitFileChange,
    GitFileStatusType,
    GitRepoState,
    STATUS_COLORS,
)
from core.git_service import GitService
from ui.diff_viewer import DiffViewerDialog
from ui.branch_dialog import BranchDialog
from ui.git_history_dialog import GitHistoryDialog
from ui.gitignore_dialog import GitignoreDialog


class GitPanel(QWidget):
    """
    Left-docked Git Source Control panel.
    """
    repo_state_changed = pyqtSignal()
    ai_prompt_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.repo_root: Optional[Path] = None
        self.current_state: GitRepoState = GitRepoState(is_repo=False)
        self._build_ui()

    def set_repo_root(self, path: Optional[Path]):
        """Sets the working repository directory and refreshes status."""
        self.repo_root = Path(path).resolve() if path else None
        self.refresh_status()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(6, 6, 6, 6)
        root_layout.setSpacing(8)

        # Header bar: Title, Branch, Actions
        header_layout = QHBoxLayout()
        header_layout.setSpacing(6)

        title_lbl = QLabel("Source Control")
        title_lbl.setStyleSheet("font-size: 11pt; font-weight: bold; color: #e6e8ef;")
        header_layout.addWidget(title_lbl)

        header_layout.addStretch(1)

        # Quick toolbar buttons: Refresh, Fetch, Pull, Push, History, .gitignore
        self.refresh_btn = QPushButton("🔄")
        self.refresh_btn.setToolTip("Refresh Git Status")
        self.refresh_btn.setFixedWidth(28)
        self.refresh_btn.setStyleSheet("background: #2a344a; color: #e6e8ef; border: 1px solid #3d4f73; border-radius: 4px; padding: 3px;")
        self.refresh_btn.clicked.connect(self.refresh_status)
        header_layout.addWidget(self.refresh_btn)

        self.pull_btn = QPushButton("⬇️")
        self.pull_btn.setToolTip("Pull from Remote")
        self.pull_btn.setFixedWidth(28)
        self.pull_btn.setStyleSheet("background: #2a344a; color: #e6e8ef; border: 1px solid #3d4f73; border-radius: 4px; padding: 3px;")
        self.pull_btn.clicked.connect(self._pull)
        header_layout.addWidget(self.pull_btn)

        self.push_btn = QPushButton("⬆️")
        self.push_btn.setToolTip("Push to Remote")
        self.push_btn.setFixedWidth(28)
        self.push_btn.setStyleSheet("background: #2a344a; color: #e6e8ef; border: 1px solid #3d4f73; border-radius: 4px; padding: 3px;")
        self.push_btn.clicked.connect(self._push)
        header_layout.addWidget(self.push_btn)

        self.history_btn = QPushButton("📜")
        self.history_btn.setToolTip("View Git History")
        self.history_btn.setFixedWidth(28)
        self.history_btn.setStyleSheet("background: #2a344a; color: #e6e8ef; border: 1px solid #3d4f73; border-radius: 4px; padding: 3px;")
        self.history_btn.clicked.connect(self._show_history)
        header_layout.addWidget(self.history_btn)

        self.gitignore_btn = QPushButton("📄")
        self.gitignore_btn.setToolTip("Generate .gitignore")
        self.gitignore_btn.setFixedWidth(28)
        self.gitignore_btn.setStyleSheet("background: #2a344a; color: #e6e8ef; border: 1px solid #3d4f73; border-radius: 4px; padding: 3px;")
        self.gitignore_btn.clicked.connect(self._show_gitignore_dialog)
        header_layout.addWidget(self.gitignore_btn)

        root_layout.addLayout(header_layout)

        # Branch Selector Bar
        self.branch_bar = QWidget()
        branch_layout = QHBoxLayout(self.branch_bar)
        branch_layout.setContentsMargins(0, 0, 0, 0)
        self.branch_btn = QPushButton("🌿 (No branch)")
        self.branch_btn.setStyleSheet(
            "background: #1e2433; color: #8ab4f8; border: 1px solid #313d54; "
            "border-radius: 4px; padding: 4px 10px; font-weight: bold; text-align: left;"
        )
        self.branch_btn.clicked.connect(self._show_branch_dialog)
        branch_layout.addWidget(self.branch_btn, 1)

        self.sync_lbl = QLabel("")
        self.sync_lbl.setStyleSheet("font-size: 9pt; color: #79869c;")
        branch_layout.addWidget(self.sync_lbl)

        root_layout.addWidget(self.branch_bar)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(3)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("QProgressBar { background: #1b1e26; border: 0; } QProgressBar::chunk { background: #65d98b; }")
        self.progress_bar.hide()
        root_layout.addWidget(self.progress_bar)

        # Non-repo Banner (shown when not a git repository)
        self.no_repo_box = QFrame()
        self.no_repo_box.setStyleSheet("background: #181b24; border: 1px solid #282f40; border-radius: 6px; padding: 12px;")
        no_repo_layout = QVBoxLayout(self.no_repo_box)
        no_repo_layout.setSpacing(8)

        self.no_repo_msg = QLabel("No Git repository found in active workspace.")
        self.no_repo_msg.setWordWrap(True)
        self.no_repo_msg.setStyleSheet("color: #9aa4b5; font-size: 9pt;")
        no_repo_layout.addWidget(self.no_repo_msg)

        init_btn = QPushButton("Initialize Repository")
        init_btn.setStyleSheet("background: #2ea043; color: white; font-weight: bold; border-radius: 4px; padding: 6px;")
        init_btn.clicked.connect(self._init_repository)
        no_repo_layout.addWidget(init_btn)

        clone_btn = QPushButton("Clone Repository…")
        clone_btn.setStyleSheet("background: #2a344a; color: #8ab4f8; border: 1px solid #3d4f73; border-radius: 4px; padding: 6px;")
        clone_btn.clicked.connect(self._clone_repository)
        no_repo_layout.addWidget(clone_btn)

        root_layout.addWidget(self.no_repo_box)
        self.no_repo_box.hide()

        # Repository Content Area (Commit Input + Changes Tree)
        self.repo_content_widget = QWidget()
        repo_content_layout = QVBoxLayout(self.repo_content_widget)
        repo_content_layout.setContentsMargins(0, 0, 0, 0)
        repo_content_layout.setSpacing(6)

        # Commit message editor
        self.commit_input = QPlainTextEdit()
        self.commit_input.setPlaceholderText("Message (Ctrl+Enter to commit)")
        self.commit_input.setFixedHeight(64)
        self.commit_input.setStyleSheet("background: #1b1e26; border: 1px solid #333d52; border-radius: 4px; padding: 4px; color: #fff;")
        repo_content_layout.addWidget(self.commit_input)

        # Commit action buttons row
        commit_btn_row = QHBoxLayout()
        commit_btn_row.setSpacing(6)

        self.commit_btn = QPushButton("✓ Commit")
        self.commit_btn.setStyleSheet("background: #0969da; color: white; font-weight: bold; border-radius: 4px; padding: 5px 12px;")
        self.commit_btn.clicked.connect(self._commit)
        commit_btn_row.addWidget(self.commit_btn, 1)

        self.ai_commit_btn = QPushButton("✨ AI Msg")
        self.ai_commit_btn.setToolTip("Generate commit message using Ollama AI from staged diff")
        self.ai_commit_btn.setStyleSheet("background: #3c2d4a; color: #d2a8ff; border: 1px solid #5d3f78; border-radius: 4px; padding: 5px 8px; font-weight: 500;")
        self.ai_commit_btn.clicked.connect(self._ai_generate_commit_message)
        commit_btn_row.addWidget(self.ai_commit_btn)

        repo_content_layout.addLayout(commit_btn_row)

        # Changes Tree (Staged & Unstaged)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setStyleSheet(
            "QTreeWidget { background: #141720; border: 1px solid #282f40; border-radius: 4px; outline: none; }"
            "QTreeWidget::item { padding: 4px; }"
            "QTreeWidget::item:selected { background: #232c3d; }"
        )
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)

        repo_content_layout.addWidget(self.tree, 1)
        root_layout.addWidget(self.repo_content_widget, 1)

    def refresh_status(self):
        """Discovers git installation and inspects working tree status."""
        if not GitService.is_git_installed():
            self.branch_bar.hide()
            self.repo_content_widget.hide()
            self.no_repo_box.show()
            self.no_repo_msg.setText(
                "⚠️ <b>Git is not installed</b> or not found in system PATH.<br><br>"
                "Install Git for Windows to enable Source Control features."
            )
            return

        if not self.repo_root or not GitService.is_git_repository(self.repo_root):
            self.branch_bar.hide()
            self.repo_content_widget.hide()
            self.no_repo_box.show()
            self.no_repo_msg.setText("No Git repository found in the active workspace.")
            return

        self.no_repo_box.hide()
        self.branch_bar.show()
        self.repo_content_widget.show()

        ok, msg, state = GitService.get_status(self.repo_root)
        if not ok:
            return

        self.current_state = state
        self.branch_btn.setText(f"🌿 {state.current_branch or 'main'}")

        # Update sync label
        sync_parts = []
        if state.ahead_count > 0:
            sync_parts.append(f"↑{state.ahead_count}")
        if state.behind_count > 0:
            sync_parts.append(f"↓{state.behind_count}")
        self.sync_lbl.setText(" ".join(sync_parts))

        # Re-populate Changes Tree
        self.tree.clear()

        # Group 1: Staged Changes
        staged_header = QTreeWidgetItem(self.tree)
        staged_header.setText(0, f"STAGED CHANGES ({len(state.staged_files)})")
        staged_header.setFont(0, QFont("Segoe UI", 8, QFont.Weight.Bold))
        staged_header.setForeground(0, QColor("#8ab4f8"))
        staged_header.setExpanded(True)

        for f in state.staged_files:
            item = QTreeWidgetItem(staged_header)
            item.setText(0, f"{f.status_type.value}  {f.path}")
            item.setForeground(0, QColor(f.status_color))
            item.setData(0, Qt.ItemDataRole.UserRole, f)

        # Group 2: Conflicts (if any)
        if state.conflict_files:
            conflict_header = QTreeWidgetItem(self.tree)
            conflict_header.setText(0, f"MERGE CONFLICTS ({len(state.conflict_files)})")
            conflict_header.setFont(0, QFont("Segoe UI", 8, QFont.Weight.Bold))
            conflict_header.setForeground(0, QColor("#e06c75"))
            conflict_header.setExpanded(True)

            for f in state.conflict_files:
                item = QTreeWidgetItem(conflict_header)
                item.setText(0, f"!  {f.path} (conflict)")
                item.setForeground(0, QColor("#e06c75"))
                item.setData(0, Qt.ItemDataRole.UserRole, f)

        # Group 3: Changes (Unstaged + Untracked)
        unstaged_count = len(state.unstaged_files) + len(state.untracked_files)
        changes_header = QTreeWidgetItem(self.tree)
        changes_header.setText(0, f"CHANGES ({unstaged_count})")
        changes_header.setFont(0, QFont("Segoe UI", 8, QFont.Weight.Bold))
        changes_header.setForeground(0, QColor("#d7dae0"))
        changes_header.setExpanded(True)

        for f in state.unstaged_files:
            item = QTreeWidgetItem(changes_header)
            item.setText(0, f"{f.status_type.value}  {f.path}")
            item.setForeground(0, QColor(f.status_color))
            item.setData(0, Qt.ItemDataRole.UserRole, f)

        for f in state.untracked_files:
            item = QTreeWidgetItem(changes_header)
            item.setText(0, f"?  {f.path}")
            item.setForeground(0, QColor(f.status_color))
            item.setData(0, Qt.ItemDataRole.UserRole, f)

        self.repo_state_changed.emit()

    def _show_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            # Right-clicked empty area
            menu = QMenu(self)
            menu.addAction("Stage All Changes", self._stage_all)
            menu.addAction("Unstage All Changes", self._unstage_all)
            menu.addAction("Discard All Changes…", self._discard_all)
            menu.exec(self.tree.viewport().mapToGlobal(pos))
            return

        file_change: Optional[GitFileChange] = item.data(0, Qt.ItemDataRole.UserRole)
        menu = QMenu(self)

        if file_change:
            # File item clicked
            menu.addAction("View Diff", lambda: self._open_diff(file_change))

            if file_change.is_staged:
                menu.addAction("Unstage Changes", lambda: self._unstage_file(file_change.path))
            else:
                menu.addAction("Stage Changes", lambda: self._stage_file(file_change.path))
                menu.addAction("Discard Changes…", lambda: self._discard_file(file_change))

            menu.addSeparator()
            ai_menu = menu.addMenu("✨ AI Assistant")
            ai_menu.addAction("Explain Changes with AI", lambda: self._ai_explain_file(file_change))
            ai_menu.addAction("Review for Potential Bugs", lambda: self._ai_review_file(file_change))

        else:
            # Header item clicked
            header_text = item.text(0)
            if "STAGED" in header_text:
                menu.addAction("Unstage All Changes", self._unstage_all)
            elif "CHANGES" in header_text:
                menu.addAction("Stage All Changes", self._stage_all)
                menu.addAction("Discard All Changes…", self._discard_all)

        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        file_change: Optional[GitFileChange] = item.data(0, Qt.ItemDataRole.UserRole)
        if file_change:
            self._open_diff(file_change)

    def _open_diff(self, file_change: GitFileChange):
        if not self.repo_root:
            return
        ok, msg, raw_diff = GitService.get_diff(
            self.repo_root, rel_file=file_change.path, staged=file_change.is_staged
        )
        dlg = DiffViewerDialog(
            file_path=file_change.path,
            raw_diff=raw_diff,
            is_staged=file_change.is_staged,
            parent=self,
        )
        dlg.exec()

    # --- Git Action Handlers ---

    def _stage_file(self, rel_path: str):
        if self.repo_root:
            GitService.stage_file(self.repo_root, rel_path)
            self.refresh_status()

    def _stage_all(self):
        if self.repo_root:
            GitService.stage_all(self.repo_root)
            self.refresh_status()

    def _unstage_file(self, rel_path: str):
        if self.repo_root:
            GitService.unstage_file(self.repo_root, rel_path)
            self.refresh_status()

    def _unstage_all(self):
        if self.repo_root:
            GitService.unstage_all(self.repo_root)
            self.refresh_status()

    def _discard_file(self, file_change: GitFileChange):
        confirm = QMessageBox.warning(
            self,
            "Confirm Discard",
            f"Are you sure you want to discard changes in '{file_change.path}'?\n\n"
            "This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes and self.repo_root:
            is_untracked = file_change.status_type == GitFileStatusType.UNTRACKED
            ok, msg = GitService.discard_file(self.repo_root, file_change.path, is_untracked=is_untracked)
            if not ok:
                QMessageBox.critical(self, "Discard Failed", msg)
            self.refresh_status()

    def _discard_all(self):
        confirm = QMessageBox.warning(
            self,
            "Confirm Discard All",
            "Are you sure you want to discard ALL uncommitted changes and untracked files?\n\n"
            "This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes and self.repo_root:
            ok, msg = GitService.discard_all(self.repo_root)
            if not ok:
                QMessageBox.critical(self, "Discard Failed", msg)
            self.refresh_status()

    def _commit(self):
        if not self.repo_root:
            return

        msg = self.commit_input.toPlainText().strip()
        if not msg:
            QMessageBox.warning(self, "Commit", "Please enter a commit message.")
            self.commit_input.setFocus()
            return

        # If no files staged, offer to stage all
        if not self.current_state.staged_files:
            if not (self.current_state.unstaged_files or self.current_state.untracked_files):
                QMessageBox.information(self, "Commit", "There are no changes to commit.")
                return

            ans = QMessageBox.question(
                self,
                "No Staged Changes",
                "There are no staged changes.\nDo you want to stage all changes and commit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ans == QMessageBox.StandardButton.Yes:
                GitService.stage_all(self.repo_root)
            else:
                return

        ok, out = GitService.commit(self.repo_root, msg)
        if ok:
            self.commit_input.clear()
            self.refresh_status()
        else:
            QMessageBox.critical(self, "Commit Failed", out)

    def _pull(self):
        if not self.repo_root:
            return
        self.progress_bar.show()
        self.progress_bar.setRange(0, 0)

        def on_done(ok, out, err):
            self.progress_bar.hide()
            self.refresh_status()
            if ok:
                QMessageBox.information(self, "Git Pull", out or "Already up to date.")
            else:
                QMessageBox.critical(self, "Git Pull Error", err or out)

        GitService.run_git_async(self.repo_root, ["pull"], on_done, self)

    def _push(self):
        if not self.repo_root:
            return
        self.progress_bar.show()
        self.progress_bar.setRange(0, 0)

        def on_done(ok, out, err):
            self.progress_bar.hide()
            self.refresh_status()
            if ok:
                QMessageBox.information(self, "Git Push", out or "Push completed successfully.")
            else:
                QMessageBox.critical(self, "Git Push Error", err or out)

        GitService.run_git_async(self.repo_root, ["push"], on_done, self)

    def _show_history(self):
        if self.repo_root:
            dlg = GitHistoryDialog(self.repo_root, self)
            dlg.exec()

    def _show_branch_dialog(self):
        if self.repo_root:
            dlg = BranchDialog(self.repo_root, self)
            dlg.branch_changed.connect(lambda _: self.refresh_status())
            dlg.exec()

    def _show_gitignore_dialog(self):
        if self.repo_root:
            dlg = GitignoreDialog(self.repo_root, self)
            dlg.exec()
            self.refresh_status()

    def _init_repository(self):
        if not self.repo_root:
            return
        ok, msg = GitService.init_repo(self.repo_root)
        if ok:
            self.refresh_status()
        else:
            QMessageBox.critical(self, "Git Init Failed", msg)

    def _clone_repository(self):
        if not self.repo_root:
            return
        url, ok = QInputDialog.getText(self, "Clone Repository", "Enter Git repository URL or path:")
        if not ok or not url:
            return

        target = self.repo_root / Path(url.strip().split("/")[-1]).stem
        self.progress_bar.show()
        self.progress_bar.setRange(0, 0)

        def on_done(success, out, err):
            self.progress_bar.hide()
            if success:
                QMessageBox.information(self, "Clone Succeeded", f"Cloned repository into:\n{target}")
                self.set_repo_root(target)
            else:
                QMessageBox.critical(self, "Clone Failed", err or out)

        GitService.run_git_async(None, ["clone", url.strip(), str(target)], on_done, self)

    # --- AI Integration Helpers ---

    def _ai_generate_commit_message(self):
        """Generates a commit message using Ollama AI based on staged diff."""
        if not self.repo_root:
            return

        # Check staged diff first, fallback to unstaged
        ok, _, diff = GitService.get_diff(self.repo_root, staged=True)
        if not diff.strip():
            ok, _, diff = GitService.get_diff(self.repo_root, staged=False)

        if not diff.strip():
            QMessageBox.information(self, "AI Commit Message", "No changes detected to generate a commit message from.")
            return

        prompt = (
            "Based on the following Git diff, write a concise, conventional commit message (1 summary line, optional bullet points):\n\n"
            f"```diff\n{diff[:3000]}\n```\n\nReturn only the commit message text."
        )
        self.ai_prompt_requested.emit(prompt)

    def _ai_explain_file(self, file_change: GitFileChange):
        if not self.repo_root:
            return
        ok, _, diff = GitService.get_diff(self.repo_root, rel_file=file_change.path, staged=file_change.is_staged)
        prompt = (
            f"Explain the modifications made in file '{file_change.path}':\n\n"
            f"```diff\n{diff[:3000]}\n```"
        )
        self.ai_prompt_requested.emit(prompt)

    def _ai_review_file(self, file_change: GitFileChange):
        if not self.repo_root:
            return
        ok, _, diff = GitService.get_diff(self.repo_root, rel_file=file_change.path, staged=file_change.is_staged)
        prompt = (
            f"Perform a code review on the changes in file '{file_change.path}'. "
            "Identify potential bugs, security issues, performance regressions, or edge cases:\n\n"
            f"```diff\n{diff[:3000]}\n```"
        )
        self.ai_prompt_requested.emit(prompt)

