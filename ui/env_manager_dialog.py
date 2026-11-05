"""
OpenArise IDE - Development Environment Manager Dialog & Settings Tab
Displays installed developer tools, manages project Python interpreters,
and provides package manager & SDK documentation.
"""

import sys
import webbrowser
from pathlib import Path
from typing import Optional, Dict
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QComboBox,
    QFileDialog,
    QMessageBox,
    QGroupBox,
    QTabWidget,
    QProgressBar,
)
from PyQt6.QtGui import QColor, QFont

from core.env_manager import EnvironmentManager, ToolInfo


class DevelopmentEnvironmentsTab(QWidget):
    """
    Development Environments component, usable both standalone and inside SettingsDialog.
    """
    interpreter_changed = pyqtSignal(str)

    def __init__(self, project_root: Optional[Path] = None, settings_manager=None, parent=None):
        super().__init__(parent)
        self.project_root = Path(project_root).resolve() if project_root else None
        self.settings_manager = settings_manager
        self._build_ui()
        self.refresh_tools(force=False)

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(12)

        # -------------------------------------------------------------
        # Section 1: Active Project Python Interpreter
        # -------------------------------------------------------------
        proj_group = QGroupBox("Project Environment")
        proj_layout = QVBoxLayout(proj_group)
        proj_layout.setSpacing(8)

        # Interpreter row
        interp_row = QHBoxLayout()
        interp_row.addWidget(QLabel("Python Interpreter:"))
        self.interpreter_combo = QComboBox()
        self.interpreter_combo.setMinimumWidth(320)
        interp_row.addWidget(self.interpreter_combo, 1)

        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_interpreter)
        interp_row.addWidget(browse_btn)

        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self._apply_interpreter)
        interp_row.addWidget(apply_btn)
        proj_layout.addLayout(interp_row)

        # Project Status Row
        self.proj_status_label = QLabel()
        self.proj_status_label.setStyleSheet("color: #8ab4f8; font-size: 9pt;")
        proj_layout.addWidget(self.proj_status_label)

        # Create venv button if missing
        venv_row = QHBoxLayout()
        self.create_venv_btn = QPushButton("Create Project .venv")
        self.create_venv_btn.clicked.connect(self._create_venv)
        venv_row.addWidget(self.create_venv_btn)
        venv_row.addStretch()
        proj_layout.addLayout(venv_row)

        root_layout.addWidget(proj_group)

        # -------------------------------------------------------------
        # Section 2: Installed Developer Tools (16 Tools)
        # -------------------------------------------------------------
        tools_group = QGroupBox("Installed Developer Toolchains")
        tools_layout = QVBoxLayout(tools_group)
        tools_layout.setSpacing(8)

        # Action bar: Filter + Refresh
        tools_action_row = QHBoxLayout()
        tools_action_row.addWidget(QLabel("Filter Category:"))
        self.category_combo = QComboBox()
        self.category_combo.addItems(["All Tools", "Language", "Package Manager", "Build Tool", "Framework SDK", "VCS"])
        self.category_combo.currentTextChanged.connect(self._filter_tools_table)
        tools_action_row.addWidget(self.category_combo)

        tools_action_row.addStretch()

        self.refresh_btn = QPushButton("Refresh Tools")
        self.refresh_btn.clicked.connect(lambda: self.refresh_tools(force=True))
        tools_action_row.addWidget(self.refresh_btn)
        tools_layout.addLayout(tools_action_row)

        # Table of 16 tools
        self.tools_table = QTableWidget(0, 5)
        self.tools_table.setHorizontalHeaderLabels(["Tool", "Status", "Version", "Executable Path", "Documentation"])
        self.tools_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tools_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tools_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tools_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.tools_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.tools_table.setAlternatingRowColors(True)
        self.tools_table.setStyleSheet("QTableWidget { gridline-color: #2b303c; }")
        tools_layout.addWidget(self.tools_table, 1)

        root_layout.addWidget(tools_group, 1)

        self._populate_interpreters()
        self._update_project_status()

    def set_project_root(self, project_root: Optional[Path]):
        self.project_root = Path(project_root).resolve() if project_root else None
        self._populate_interpreters()
        self._update_project_status()

    def _populate_interpreters(self):
        self.interpreter_combo.clear()
        detected = EnvironmentManager.detect_python_interpreters(self.project_root)
        active = EnvironmentManager.get_project_interpreter(self.project_root, self.settings_manager)

        selected_idx = 0
        for idx, p in enumerate(detected):
            self.interpreter_combo.addItem(str(p), str(p))
            if str(p) == str(active):
                selected_idx = idx

        if self.interpreter_combo.count() > 0:
            self.interpreter_combo.setCurrentIndex(selected_idx)

    def _update_project_status(self):
        if not self.project_root:
            self.proj_status_label.setText("No project folder open.")
            self.create_venv_btn.setEnabled(False)
            return

        env_info = EnvironmentManager.detect_project_environment(self.project_root)
        parts = []
        if env_info["venv_exists"]:
            parts.append("Project Virtualenv (.venv): Active")
            self.create_venv_btn.setEnabled(False)
            self.create_venv_btn.setText(".venv Already Exists")
        else:
            parts.append("Project Virtualenv (.venv): Not Found")
            self.create_venv_btn.setEnabled(True)
            self.create_venv_btn.setText("Create Project .venv")

        if env_info["package_manager"]:
            parts.append(f"Node Package Manager: {env_info['package_manager']}")

        self.proj_status_label.setText(" | ".join(parts))

    def _browse_interpreter(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Python Interpreter",
            "",
            "Python Executable (python.exe python);;All Files (*)",
        )
        if file_path:
            p = Path(file_path).resolve()
            # Add and select
            self.interpreter_combo.addItem(str(p), str(p))
            self.interpreter_combo.setCurrentIndex(self.interpreter_combo.count() - 1)

    def _apply_interpreter(self):
        selected = self.interpreter_combo.currentText()
        if not selected:
            return
        p = Path(selected).resolve()
        if not p.exists():
            QMessageBox.warning(self, "Invalid Interpreter", f"The executable does not exist:\n{p}")
            return

        if self.project_root and self.settings_manager:
            EnvironmentManager.set_project_interpreter(self.project_root, p, self.settings_manager)
            QMessageBox.information(self, "Interpreter Saved", f"Project interpreter set to:\n{p}")
        else:
            QMessageBox.information(self, "Interpreter Selected", f"Interpreter selected:\n{p}")

        self.interpreter_changed.emit(str(p))

    def _create_venv(self):
        if not self.project_root:
            return
        target = self.project_root / ".venv"
        success, msg = EnvironmentManager.create_virtualenv(target)
        if success:
            QMessageBox.information(self, "Virtualenv Created", f"Virtual environment created at:\n{target}")
            self._populate_interpreters()
            self._update_project_status()
        else:
            QMessageBox.critical(self, "Virtualenv Failed", f"Could not create virtual environment:\n{msg}")

    def refresh_tools(self, force: bool = False):
        tools = EnvironmentManager.detect_all_tools(force_refresh=force)
        self._all_tools = tools
        self._filter_tools_table(self.category_combo.currentText())

    def _filter_tools_table(self, filter_cat: str):
        if not hasattr(self, "_all_tools"):
            return

        tools = self._all_tools
        self.tools_table.setRowCount(0)

        for name, info in tools.items():
            if filter_cat != "All Tools" and info.category.lower() != filter_cat.lower():
                continue

            row = self.tools_table.rowCount()
            self.tools_table.insertRow(row)

            # Tool name
            name_item = QTableWidgetItem(info.name)
            name_item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            self.tools_table.setItem(row, 0, name_item)

            # Status pill
            status_item = QTableWidgetItem("✓ Installed" if info.installed else "✗ Missing")
            status_item.setForeground(QColor("#81c995" if info.installed else "#f28b82"))
            self.tools_table.setItem(row, 1, status_item)

            # Version
            ver_item = QTableWidgetItem(info.version if info.installed else "—")
            self.tools_table.setItem(row, 2, ver_item)

            # Executable path
            path_item = QTableWidgetItem(info.executable_path or "Not in PATH")
            path_item.setFont(QFont("Consolas", 8))
            self.tools_table.setItem(row, 3, path_item)

            # Documentation Link
            doc_btn = QPushButton("Official Site")
            doc_btn.setFixedHeight(24)
            doc_url = info.doc_url
            doc_btn.clicked.connect(lambda checked, url=doc_url: webbrowser.open(url) if url else None)
            self.tools_table.setCellWidget(row, 4, doc_btn)


class EnvironmentManagerDialog(QDialog):
    """
    Dedicated modal dialog for managing development environments.
    """
    def __init__(self, project_root: Optional[Path] = None, settings_manager=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Development Environment Manager")
        self.resize(850, 600)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        self.tab_widget = DevelopmentEnvironmentsTab(
            project_root=project_root,
            settings_manager=settings_manager,
            parent=self,
        )
        layout.addWidget(self.tab_widget, 1)

        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self.accept)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

