"""
Git Branch Manager Dialog for OpenArise IDE.
Allows creating, switching, and deleting branches safely.
"""

from pathlib import Path
from typing import List, Optional
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QPushButton,
    QMessageBox,
    QInputDialog,
)

from core.git_models import GitBranch
from core.git_service import GitService


class BranchDialog(QDialog):
    """Dialog for creating, switching, and managing Git branches."""
    branch_changed = pyqtSignal(str)

    def __init__(self, repo_path: Path, parent=None):
        super().__init__(parent)
        self.repo_path = Path(repo_path).resolve()
        self.branches: List[GitBranch] = []
        self.current_branch_name = ""

        self.setWindowTitle(f"Branches — {self.repo_path.name}")
        self.resize(520, 460)
        self.setStyleSheet("background-color: #171920; color: #e6e8ef;")
        self._build_ui()
        self.load_branches()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(14, 14, 14, 14)
        root_layout.setSpacing(10)

        # Header
        header = QLabel("🌿 Git Branch Management")
        header.setStyleSheet("font-size: 11pt; font-weight: bold; color: #ffffff;")
        root_layout.addWidget(header)

        # Branch creation row
        create_row = QHBoxLayout()
        self.new_branch_input = QLineEdit()
        self.new_branch_input.setPlaceholderText("New branch name (e.g. feature/my-work)…")
        self.new_branch_input.setStyleSheet("background: #1b1e26; border: 1px solid #333d52; border-radius: 4px; padding: 5px; color: #fff;")
        create_row.addWidget(self.new_branch_input, 1)

        create_btn = QPushButton("Create Branch")
        create_btn.setStyleSheet("background: #2ea043; color: white; font-weight: bold; border-radius: 4px; padding: 5px 12px;")
        create_btn.clicked.connect(self._create_branch)
        create_row.addWidget(create_btn)

        root_layout.addLayout(create_row)

        # Branch List
        list_label = QLabel("Available Branches:")
        list_label.setStyleSheet("color: #79869c; font-size: 9pt;")
        root_layout.addWidget(list_label)

        self.branch_list = QListWidget()
        self.branch_list.setStyleSheet(
            "QListWidget { background: #13151b; border: 1px solid #282f40; border-radius: 4px; outline: none; }"
            "QListWidget::item { padding: 8px; border-bottom: 1px solid #1c202a; }"
            "QListWidget::item:selected { background: #232c3d; }"
        )
        self.branch_list.itemDoubleClicked.connect(self._switch_branch)
        root_layout.addWidget(self.branch_list, 1)

        # Action Buttons (Switch, Delete, Close)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.switch_btn = QPushButton("Switch to Branch")
        self.switch_btn.setStyleSheet("background: #0969da; color: white; font-weight: bold; border-radius: 4px; padding: 6px 14px;")
        self.switch_btn.clicked.connect(self._switch_branch)
        btn_row.addWidget(self.switch_btn)

        self.delete_btn = QPushButton("Delete Branch")
        self.delete_btn.setStyleSheet("background: #a42c2c; color: white; border-radius: 4px; padding: 6px 14px;")
        self.delete_btn.clicked.connect(self._delete_branch)
        btn_row.addWidget(self.delete_btn)

        btn_row.addStretch(1)

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet("background: #2a3346; color: #e6e8ef; border-radius: 4px; padding: 6px 14px;")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)

        root_layout.addLayout(btn_row)

    def load_branches(self):
        ok, msg, branches = GitService.get_branches(self.repo_path)
        self.branches = branches if ok else []
        self.branch_list.clear()

        for b in self.branches:
            item = QListWidgetItem(self.branch_list)
            if b.is_current:
                self.current_branch_name = b.name
                item.setText(f"● {b.name} (HEAD)")
                item.setForeground(Qt.GlobalColor.green)
            elif b.is_remote:
                item.setText(f"  {b.name} [remote]")
                item.setForeground(Qt.GlobalColor.gray)
            else:
                item.setText(f"  {b.name}")
            item.setData(Qt.ItemDataRole.UserRole, b)
            self.branch_list.addItem(item)

    def _create_branch(self):
        name = self.new_branch_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Invalid Name", "Branch name cannot be empty.")
            return

        ok, msg = GitService.create_branch(self.repo_path, name)
        if ok:
            self.new_branch_input.clear()
            self.load_branches()
            # Ask if user wants to switch to the new branch immediately
            ans = QMessageBox.question(
                self,
                "Branch Created",
                f"Branch '{name}' created successfully.\nDo you want to switch to it now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ans == QMessageBox.StandardButton.Yes:
                ok_sw, msg_sw = GitService.switch_branch(self.repo_path, name)
                if ok_sw:
                    self.branch_changed.emit(name)
                    self.load_branches()
                else:
                    QMessageBox.warning(self, "Switch Failed", msg_sw)
        else:
            QMessageBox.critical(self, "Branch Creation Failed", msg)

    def _switch_branch(self):
        item = self.branch_list.currentItem()
        if not item:
            return
        branch: GitBranch = item.data(Qt.ItemDataRole.UserRole)
        if branch.is_current:
            return  # Already on this branch

        # Warn if uncommitted changes exist
        ok_st, _, state = GitService.get_status(self.repo_path)
        if ok_st and not state.is_clean:
            ans = QMessageBox.warning(
                self,
                "Uncommitted Changes",
                "You have uncommitted changes in your working tree.\n"
                "Switching branches may conflict with these changes.\n\n"
                "Do you wish to proceed?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ans != QMessageBox.StandardButton.Yes:
                return

        ok, msg = GitService.switch_branch(self.repo_path, branch.name)
        if ok:
            self.branch_changed.emit(branch.name)
            self.load_branches()
            self.accept()
        else:
            QMessageBox.critical(self, "Switch Failed", msg)

    def _delete_branch(self):
        item = self.branch_list.currentItem()
        if not item:
            return
        branch: GitBranch = item.data(Qt.ItemDataRole.UserRole)

        # STRICT SAFETY: Prevent deleting current branch
        if branch.is_current:
            QMessageBox.critical(
                self,
                "Cannot Delete Active Branch",
                f"Cannot delete branch '{branch.name}' because it is currently checked out.\n"
                "Switch to a different branch first."
            )
            return

        confirm = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete branch '{branch.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            ok, msg = GitService.delete_branch(self.repo_path, branch.name)
            if ok:
                self.load_branches()
            else:
                # Prompt if unmerged and force deletion is needed
                force_ans = QMessageBox.warning(
                    self,
                    "Branch Not Fully Merged",
                    f"{msg}\n\nForce delete branch '{branch.name}' (-D)?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if force_ans == QMessageBox.StandardButton.Yes:
                    f_ok, f_msg = GitService.delete_branch(self.repo_path, branch.name, force=True)
                    if f_ok:
                        self.load_branches()
                    else:
                        QMessageBox.critical(self, "Delete Failed", f_msg)

