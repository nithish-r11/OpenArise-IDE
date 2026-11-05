"""
OpenArise IDE - New Project Multi-Step Wizard
A 6-step guided wizard for configuring and scaffolding production-ready projects.
"""

import sys
from pathlib import Path
from typing import Optional, List, Dict
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QWidget,
    QFileDialog,
    QListWidget,
    QListWidgetItem,
    QCheckBox,
    QTreeWidget,
    QTreeWidgetItem,
    QProgressBar,
    QRadioButton,
    QButtonGroup,
    QMessageBox,
    QFrame,
)
from PyQt6.QtGui import QFont, QColor

from core.project_builder import ProjectBuilder, ProjectTemplate


class NewProjectWizardDialog(QDialog):
    """
    Multi-step New Project Wizard Dialog with Next / Back / Cancel navigation.
    """
    project_created = pyqtSignal(str)  # Emits target_dir path on success

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Project Wizard")
        self.resize(720, 560)
        self.setModal(True)

        # Wizard state
        self.current_step = 0
        self.selected_template_id = "python_app"
        default_dir = Path.home() / "OpenAriseProjects"
        self.destination_dir = str(default_dir)

        self._build_ui()
        self._update_step_view()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(14)

        # -------------------------------------------------------------
        # Header: Step title and progress indicator
        # -------------------------------------------------------------
        header_widget = QWidget()
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)

        self.step_indicator_label = QLabel("Step 1 of 6")
        self.step_indicator_label.setStyleSheet("color: #8ab4f8; font-weight: bold; font-size: 11pt;")
        header_layout.addWidget(self.step_indicator_label)

        self.step_title_label = QLabel("Project Name & Destination")
        title_font = QFont("Segoe UI", 14, QFont.Weight.Bold)
        self.step_title_label.setFont(title_font)
        self.step_title_label.setStyleSheet("color: #ffffff;")
        header_layout.addWidget(self.step_title_label)

        self.step_desc_label = QLabel("Specify the name and target location for your new project.")
        self.step_desc_label.setStyleSheet("color: #9aa0a6;")
        header_layout.addWidget(self.step_desc_label)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("background-color: #2e3440;")
        header_layout.addWidget(line)

        root_layout.addWidget(header_widget)

        # -------------------------------------------------------------
        # Stacked Pages
        # -------------------------------------------------------------
        self.stack = QStackedWidget()

        # Step 1: Name and Destination
        self.stack.addWidget(self._create_step1_page())
        # Step 2: Template Selection
        self.stack.addWidget(self._create_step2_page())
        # Step 3: Git & Environment Setup
        self.stack.addWidget(self._create_step3_page())
        # Step 4: Optional Dependencies Setup
        self.stack.addWidget(self._create_step4_page())
        # Step 5: File Structure Preview
        self.stack.addWidget(self._create_step5_page())
        # Step 6: Confirmation & Creation
        self.stack.addWidget(self._create_step6_page())

        root_layout.addWidget(self.stack, 1)

        # -------------------------------------------------------------
        # Footer: Back, Next, Cancel Navigation
        # -------------------------------------------------------------
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 8, 0, 0)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedWidth(90)
        self.cancel_btn.clicked.connect(self.reject)
        footer_layout.addWidget(self.cancel_btn)

        footer_layout.addStretch()

        self.back_btn = QPushButton("Back")
        self.back_btn.setFixedWidth(90)
        self.back_btn.clicked.connect(self.go_back)
        footer_layout.addWidget(self.back_btn)

        self.next_btn = QPushButton("Next")
        self.next_btn.setFixedWidth(110)
        self.next_btn.setDefault(True)
        self.next_btn.setStyleSheet("QPushButton { background-color: #1a73e8; color: white; font-weight: bold; } QPushButton:hover { background-color: #1b66c9; }")
        self.next_btn.clicked.connect(self.go_next)
        footer_layout.addWidget(self.next_btn)

        root_layout.addLayout(footer_layout)

    # -----------------------------------------------------------------
    # Step Pages Builders
    # -----------------------------------------------------------------

    def _create_step1_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        layout.addWidget(QLabel("Project Name:"))
        self.name_input = QLineEdit("my_openarise_app")
        self.name_input.textChanged.connect(self._validate_step1)
        layout.addWidget(self.name_input)

        layout.addWidget(QLabel("Destination Directory:"))
        dest_row = QHBoxLayout()
        self.dest_input = QLineEdit(self.destination_dir)
        self.dest_input.textChanged.connect(self._validate_step1)
        dest_row.addWidget(self.dest_input, 1)

        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_destination)
        dest_row.addWidget(browse_btn)
        layout.addLayout(dest_row)

        layout.addWidget(QLabel("Final Project Path:"))
        self.final_path_label = QLabel()
        self.final_path_label.setStyleSheet("color: #8ab4f8; font-family: Consolas; padding: 4px; background: #1f232d; border-radius: 4px;")
        layout.addWidget(self.final_path_label)

        self.step1_error_label = QLabel()
        self.step1_error_label.setStyleSheet("color: #f28b82; font-size: 9pt;")
        layout.addWidget(self.step1_error_label)

        layout.addStretch()
        return page

    def _create_step2_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(10)

        # Filter buttons
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter by Language:"))
        self.filter_group = QButtonGroup(page)
        for i, lang in enumerate(["All", "Python", "JavaScript / TypeScript"]):
            rb = QRadioButton(lang)
            if i == 0:
                rb.setChecked(True)
            self.filter_group.addButton(rb, i)
            filter_layout.addWidget(rb)
        filter_layout.addStretch()
        self.filter_group.idClicked.connect(self._on_template_filter_changed)
        layout.addLayout(filter_layout)

        # Template list widget
        self.template_list = QListWidget()
        self.template_list.setStyleSheet(
            "QListWidget::item { padding: 10px; border-bottom: 1px solid #2a303c; border-radius: 4px; }"
            "QListWidget::item:selected { background: #2f3b52; color: #ffffff; }"
        )
        self.template_list.currentRowChanged.connect(self._on_template_selected)
        layout.addWidget(self.template_list, 1)

        self._populate_template_list()
        return page

    def _create_step3_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)

        layout.addWidget(QLabel("Author Name:"))
        self.author_input = QLineEdit("OpenArise Developer")
        layout.addWidget(self.author_input)

        self.git_check = QCheckBox("Initialize a local Git repository")
        self.git_check.setChecked(True)
        layout.addWidget(self.git_check)

        self.venv_check = QCheckBox("Create project virtual environment (.venv)")
        self.venv_check.setChecked(True)
        layout.addWidget(self.venv_check)

        self.env_note_label = QLabel(
            "Tip: Creating a virtual environment isolates your project packages from the system Python."
        )
        self.env_note_label.setStyleSheet("color: #9aa0a6; font-size: 9pt;")
        layout.addWidget(self.env_note_label)

        layout.addStretch()
        return page

    def _create_step4_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)

        note = QLabel(
            "Security Policy: OpenArise IDE never runs package installation commands "
            "(pip install or npm install) without explicit user authorization."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #fdd663; padding: 10px; background: #28241b; border: 1px solid #5a4b1c; border-radius: 4px;")
        layout.addWidget(note)

        self.dep_details_label = QLabel()
        self.dep_details_label.setWordWrap(True)
        self.dep_details_label.setStyleSheet("color: #e6e8ef; padding: 4px;")
        layout.addWidget(self.dep_details_label)

        self.install_deps_check = QCheckBox("I approve installing template dependencies after project creation")
        self.install_deps_check.setChecked(False)
        layout.addWidget(self.install_deps_check)

        layout.addStretch()
        return page

    def _create_step5_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(10)

        layout.addWidget(QLabel("Project File Structure Preview:"))
        self.preview_tree = QTreeWidget()
        self.preview_tree.setHeaderLabels(["Files & Directories"])
        layout.addWidget(self.preview_tree, 1)

        return page

    def _create_step6_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)

        layout.addWidget(QLabel("Review Project Settings:"))
        self.summary_label = QLabel()
        self.summary_label.setStyleSheet(
            "background: #1f232d; border: 1px solid #343b49; border-radius: 6px; padding: 12px; font-family: Segoe UI;"
        )
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        self.creation_progress = QProgressBar()
        self.creation_progress.setRange(0, 100)
        self.creation_progress.setValue(0)
        self.creation_progress.setTextVisible(True)
        self.creation_progress.hide()
        layout.addWidget(self.creation_progress)

        self.creation_status = QLabel("")
        self.creation_status.setStyleSheet("color: #8ab4f8;")
        layout.addWidget(self.creation_status)

        layout.addStretch()
        return page

    # -----------------------------------------------------------------
    # Step Navigation & Logic
    # -----------------------------------------------------------------

    def _browse_destination(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Destination Folder", self.dest_input.text())
        if folder:
            self.dest_input.setText(folder)

    def _validate_step1(self) -> bool:
        name = self.name_input.text()
        dest = Path(self.dest_input.text().strip()) if self.dest_input.text().strip() else None

        valid, err, target = ProjectBuilder.validate_destination(name, dest)
        if target:
            self.final_path_label.setText(str(target))
        else:
            self.final_path_label.setText("—")

        if not valid:
            self.step1_error_label.setText(err)
            if hasattr(self, "next_btn"):
                self.next_btn.setEnabled(False)
            return False
        else:
            self.step1_error_label.setText("")
            if hasattr(self, "next_btn"):
                self.next_btn.setEnabled(True)
            return True

    def _populate_template_list(self, language_filter: Optional[str] = None):
        self.template_list.clear()
        templates = ProjectBuilder.list_templates(language=language_filter)
        selected_row = 0
        for i, tpl in enumerate(templates):
            item = QListWidgetItem()
            item.setText(f"{tpl.name} ({tpl.language})\nCategory: {tpl.category}\n{tpl.description}")
            item.setData(Qt.ItemDataRole.UserRole, tpl.id)
            self.template_list.addItem(item)
            if tpl.id == self.selected_template_id:
                selected_row = i

        if self.template_list.count() > 0:
            self.template_list.setCurrentRow(selected_row)

    def _on_template_filter_changed(self, btn_id: int):
        filter_map = {0: None, 1: "Python", 2: "JavaScript / TypeScript"}
        self._populate_template_list(language_filter=filter_map.get(btn_id))

    def _on_template_selected(self, row: int):
        item = self.template_list.item(row)
        if item:
            self.selected_template_id = item.data(Qt.ItemDataRole.UserRole)
            # Update venv checkbox visibility/enablement based on language
            tpl = ProjectBuilder.get_template(self.selected_template_id)
            if tpl and hasattr(self, "venv_check"):
                is_python = (tpl.language == "Python")
                self.venv_check.setEnabled(is_python)
                self.venv_check.setChecked(is_python)

    def _refresh_preview_tree(self):
        self.preview_tree.clear()
        name = self.name_input.text().strip()
        preview_entries = ProjectBuilder.preview_project(self.selected_template_id, name)

        root_item = QTreeWidgetItem(self.preview_tree, [f"📁 {name}/"])
        root_item.setExpanded(True)

        items_map = {"": root_item}
        for rel_path, is_dir in preview_entries:
            parts = rel_path.split("/")
            parent_key = "/".join(parts[:-1])
            parent_node = items_map.get(parent_key, root_item)

            icon = "📁 " if is_dir else "📄 "
            node = QTreeWidgetItem(parent_node, [f"{icon}{parts[-1]}"])
            node.setExpanded(True)
            if is_dir:
                items_map[rel_path] = node

    def _update_step_view(self):
        self.stack.setCurrentIndex(self.current_step)
        self.back_btn.setEnabled(self.current_step > 0)

        step_titles = [
            ("Step 1 of 6", "Project Name & Destination", "Specify the name and target location for your new project."),
            ("Step 2 of 6", "Template & Language", "Select an official project starter template."),
            ("Step 3 of 6", "Git & Environment Configuration", "Configure version control and virtual environment options."),
            ("Step 4 of 6", "Dependency Installation Setup", "Review and authorize dependency installation."),
            ("Step 5 of 6", "Project Structure Preview", "Inspect the files and folders to be created."),
            ("Step 6 of 6", "Confirm & Create", "Review your settings and create your project."),
        ]

        step_ind, title, desc = step_titles[self.current_step]
        self.step_indicator_label.setText(step_ind)
        self.step_title_label.setText(title)
        self.step_desc_label.setText(desc)

        if self.current_step == 0:
            self._validate_step1()
        else:
            self.next_btn.setEnabled(True)

        if self.current_step == 3:
            tpl = ProjectBuilder.get_template(self.selected_template_id)
            if tpl and tpl.language == "Python":
                self.dep_details_label.setText(
                    f"Template '{tpl.name}' includes a requirements.txt file. "
                    "If approved, OpenArise will install dependencies into the project virtual environment."
                )
            elif tpl:
                self.dep_details_label.setText(
                    f"Template '{tpl.name}' includes a package.json file. "
                    "If approved, OpenArise will install packages using your detected package manager."
                )

        if self.current_step == 4:
            self._refresh_preview_tree()

        if self.current_step == 5:
            self.next_btn.setText("Create Project")
            tpl = ProjectBuilder.get_template(self.selected_template_id)
            tpl_name = tpl.name if tpl else self.selected_template_id
            name = self.name_input.text().strip()
            dest = self.dest_input.text().strip()
            summary_text = (
                f"<b>Project Name:</b> {name}<br>"
                f"<b>Template:</b> {tpl_name}<br>"
                f"<b>Destination:</b> {dest}/{name}<br>"
                f"<b>Author:</b> {self.author_input.text().strip()}<br>"
                f"<b>Git Repository:</b> {'Yes (git init)' if self.git_check.isChecked() else 'No'}<br>"
                f"<b>Python Virtualenv:</b> {'Yes (.venv)' if self.venv_check.isChecked() else 'No'}<br>"
                f"<b>Install Dependencies:</b> {'Approved by user' if self.install_deps_check.isChecked() else 'Skip (manual installation later)'}"
            )
            self.summary_label.setText(summary_text)
        else:
            self.next_btn.setText("Next")

    def go_back(self):
        if self.current_step > 0:
            self.current_step -= 1
            self._update_step_view()

    def go_next(self):
        if self.current_step == 0:
            if not self._validate_step1():
                return
        if self.current_step < 5:
            self.current_step += 1
            self._update_step_view()
        else:
            # Final step: execute creation
            self._execute_creation()

    def _execute_creation(self):
        name = self.name_input.text().strip()
        dest_dir = Path(self.dest_input.text().strip())
        author = self.author_input.text().strip()
        init_git = self.git_check.isChecked()
        create_venv = self.venv_check.isChecked()

        self.creation_progress.show()
        self.next_btn.setEnabled(False)
        self.back_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)

        def progress_cb(msg: str, pct: int):
            self.creation_status.setText(msg)
            self.creation_progress.setValue(pct)

        success, err, target_path = ProjectBuilder.create_project(
            template_id=self.selected_template_id,
            name=name,
            dest_dir=dest_dir,
            init_git=init_git,
            create_venv=create_venv,
            author=author,
            progress_callback=progress_cb,
        )

        if not success:
            self.creation_status.setText(f"Error: {err}")
            self.next_btn.setEnabled(True)
            self.back_btn.setEnabled(True)
            self.cancel_btn.setEnabled(True)
            QMessageBox.critical(self, "Project Creation Failed", err)
            return

        self.creation_status.setText("Success! Opening project…")
        self.project_created.emit(str(target_path))
        QTimer.singleShot(400, self.accept)
