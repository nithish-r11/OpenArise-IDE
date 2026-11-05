"""
OpenArise IDE - AI Website Builder Dialog
Modal interface for creating complete website projects from natural-language prompts.
Coordinates AI generation with local Ollama, offline scaffolding fallback,
and multi-file diff review and approval before writing to disk.
"""

from __future__ import annotations
import shutil
from pathlib import Path
from typing import Optional, List

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QProgressBar,
    QFileDialog,
    QMessageBox,
    QFrame,
    QWidget,
)

from core.agent_models import FileChangeRecord
from core.project_builder import ProjectBuilder
from core.website_generator import AIWebsiteGenerator, WebsiteSpec
from ui.agent_diff_dialog import AgentDiffDialog


EXAMPLE_PROMPTS = [
    (
        "Modern Personal Portfolio",
        "Create a modern responsive personal portfolio website with Home, About, Skills, Projects and Contact sections. "
        "Use a premium dark theme, modern typography, subtle animations and mobile-friendly navigation. "
        "Create all required files and make it fully runnable locally."
    ),
    (
        "E-Commerce Storefront",
        "Create a modern professional e-commerce website with a homepage, product listing, product details, "
        "shopping cart, login page and responsive mobile design."
    ),
    (
        "SaaS Landing Page",
        "Create a sleek SaaS landing page for an AI developer tool with features grid, pricing tables, "
        "interactive FAQ accordion, testimonials, and newsletter signup form."
    ),
]


class WebsiteGenerationWorker(QThread):
    """Asynchronous worker for generating website files with Ollama."""
    progress = pyqtSignal(str, int)
    finished_records = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, spec: WebsiteSpec, parent=None):
        super().__init__(parent)
        self.spec = spec
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            def update(msg: str, pct: int):
                if not self._is_cancelled:
                    self.progress.emit(msg, pct)

            records = AIWebsiteGenerator.generate_website(self.spec, progress_callback=update)
            if not self._is_cancelled:
                self.finished_records.emit(records)
        except Exception as exc:
            if not self._is_cancelled:
                self.failed.emit(str(exc))


class WebsiteBuilderDialog(QDialog):
    """
    Dialog for configuring and generating AI-powered websites.
    """
    website_created = pyqtSignal(str)  # Emits target project path

    def __init__(self, default_model: str = "qwen2.5-coder:7b", initial_dest: Optional[Path] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Website with AI — OpenArise IDE")
        self.resize(760, 640)
        self.setModal(True)
        self.default_model = default_model
        self.worker: Optional[WebsiteGenerationWorker] = None

        default_parent = initial_dest or (Path.home() / "OpenAriseProjects")
        self.default_destination = str(default_parent)

        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(14)

        # Header Title
        title_label = QLabel("AI Prompt-to-Website Builder")
        title_label.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #ffffff;")
        root.addWidget(title_label)

        sub_label = QLabel(
            "Describe your website in natural language. Local Ollama AI will generate complete, "
            "production-ready files for your review and local preview."
        )
        sub_label.setWordWrap(True)
        sub_label.setStyleSheet("color: #9aa0a6; font-size: 10pt;")
        root.addWidget(sub_label)

        # -------------------------------------------------------------
        # Input 1 & 2: Name and Destination
        # -------------------------------------------------------------
        form_frame = QFrame()
        form_frame.setStyleSheet("background-color: #1a1a22; border-radius: 8px; padding: 12px;")
        form_layout = QVBoxLayout(form_frame)
        form_layout.setSpacing(10)

        # Name
        name_box = QHBoxLayout()
        name_lbl = QLabel("Website Name:")
        name_lbl.setFixedWidth(130)
        name_lbl.setStyleSheet("font-weight: 500; color: #e0e0e0;")
        self.name_edit = QLineEdit("my-ai-website")
        name_box.addWidget(name_lbl)
        name_box.addWidget(self.name_edit)
        form_layout.addLayout(name_box)

        # Destination
        dest_box = QHBoxLayout()
        dest_lbl = QLabel("Destination Folder:")
        dest_lbl.setFixedWidth(130)
        dest_lbl.setStyleSheet("font-weight: 500; color: #e0e0e0;")
        self.dest_edit = QLineEdit(self.default_destination)
        self.browse_btn = QPushButton("Browse…")
        self.browse_btn.clicked.connect(self._browse_destination)
        dest_box.addWidget(dest_lbl)
        dest_box.addWidget(self.dest_edit)
        dest_box.addWidget(self.browse_btn)
        form_layout.addLayout(dest_box)

        # Technology Selection
        tech_box = QHBoxLayout()
        tech_lbl = QLabel("Technology:")
        tech_lbl.setFixedWidth(130)
        tech_lbl.setStyleSheet("font-weight: 500; color: #e0e0e0;")
        self.tech_group = QButtonGroup(self)
        self.radio_html = QRadioButton("HTML + CSS + JavaScript")
        self.radio_html.setChecked(True)
        self.radio_react = QRadioButton("React + Vite")
        self.tech_group.addButton(self.radio_html)
        self.tech_group.addButton(self.radio_react)
        tech_box.addWidget(tech_lbl)
        tech_box.addWidget(self.radio_html)
        tech_box.addWidget(self.radio_react)
        tech_box.addStretch()
        form_layout.addLayout(tech_box)

        # Multi-page checkbox
        self.multipage_check = QCheckBox("Multi-Page Website (creates index.html, about.html, contact.html)")
        self.multipage_check.setStyleSheet("color: #d0d0d8; margin-left: 130px;")
        form_layout.addWidget(self.multipage_check)

        root.addWidget(form_frame)

        # -------------------------------------------------------------
        # Input 3: Natural Language Prompt Editor
        # -------------------------------------------------------------
        prompt_header = QHBoxLayout()
        prompt_lbl = QLabel("Website Description / Prompt:")
        prompt_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        prompt_lbl.setStyleSheet("color: #ffffff;")
        prompt_header.addWidget(prompt_lbl)
        prompt_header.addStretch()

        self.example_btn = QPushButton("Load Example Prompt…")
        self.example_btn.setStyleSheet("font-size: 9pt;")
        self.example_btn.clicked.connect(self._load_example_prompt)
        prompt_header.addWidget(self.example_btn)
        root.addLayout(prompt_header)

        self.prompt_edit = QPlainTextEdit()
        self.prompt_edit.setPlaceholderText(
            "e.g. Create a modern responsive personal portfolio website with Home, About, Skills, "
            "Projects and Contact sections. Use a premium dark theme, modern typography, subtle animations "
            "and mobile-friendly navigation..."
        )
        self.prompt_edit.setPlainText(EXAMPLE_PROMPTS[0][1])
        self.prompt_edit.setStyleSheet("""
            QPlainTextEdit {
                background-color: #16161c;
                border: 1px solid #33333d;
                border-radius: 6px;
                padding: 10px;
                color: #f0f0f5;
                font-family: 'Segoe UI', sans-serif;
                font-size: 10pt;
            }
        """)
        root.addWidget(self.prompt_edit)

        # Model Selector
        model_row = QHBoxLayout()
        model_lbl = QLabel("AI Model:")
        model_lbl.setStyleSheet("color: #9aa0a6;")
        self.model_combo = QComboBox()
        self.model_combo.addItem(self.default_model)
        self.model_combo.setEditable(True)
        self.model_combo.setMinimumWidth(220)
        model_row.addWidget(model_lbl)
        model_row.addWidget(self.model_combo)
        model_row.addStretch()
        root.addLayout(model_row)

        # -------------------------------------------------------------
        # Progress & Status Bar
        # -------------------------------------------------------------
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.hide()
        root.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #8ab4f8; font-size: 9pt;")
        self.status_label.hide()
        root.addWidget(self.status_label)

        # -------------------------------------------------------------
        # Footer Action Buttons
        # -------------------------------------------------------------
        bottom_bar = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self._handle_cancel)
        bottom_bar.addWidget(self.cancel_btn)
        bottom_bar.addStretch()

        self.generate_btn = QPushButton("Generate Complete Website")
        self.generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #6366f1;
                color: #ffffff;
                font-weight: bold;
                padding: 8px 18px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #4f46e5;
            }
        """)
        self.generate_btn.clicked.connect(self._start_generation)
        bottom_bar.addWidget(self.generate_btn)
        root.addLayout(bottom_bar)

    def _browse_destination(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Project Destination Folder", self.dest_edit.text())
        if folder:
            self.dest_edit.setText(folder)

    def _load_example_prompt(self):
        # Rotate or cycle through example prompts
        current = self.prompt_edit.toPlainText().strip()
        next_prompt = EXAMPLE_PROMPTS[0][1]
        for i, (title, text) in enumerate(EXAMPLE_PROMPTS):
            if text.strip() == current:
                next_prompt = EXAMPLE_PROMPTS[(i + 1) % len(EXAMPLE_PROMPTS)][1]
                break
        self.prompt_edit.setPlainText(next_prompt)

    def _handle_cancel(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(1000)
        self.reject()

    def _start_generation(self):
        name = self.name_edit.text().strip()
        dest = self.dest_edit.text().strip()
        prompt = self.prompt_edit.toPlainText().strip()
        tech = "react" if self.radio_react.isChecked() else "html"
        is_multipage = self.multipage_check.isChecked()
        model = self.model_combo.currentText().strip() or self.default_model

        # Validations
        val_name_ok, val_name_err = ProjectBuilder.validate_project_name(name)
        if not val_name_ok:
            QMessageBox.warning(self, "Invalid Website Name", val_name_err)
            self.name_edit.setFocus()
            return

        dest_path = Path(dest).resolve()
        if not dest_path.exists():
            try:
                dest_path.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                QMessageBox.critical(self, "Destination Error", f"Cannot create destination folder:\n{exc}")
                return

        target_project_dir = dest_path / name
        if target_project_dir.exists() and any(target_project_dir.iterdir()):
            QMessageBox.warning(
                self,
                "Project Folder Exists",
                f"A folder named '{name}' already exists in the selected destination.\n"
                "Please choose a different name or destination folder."
            )
            return

        if len(prompt) < 5:
            QMessageBox.warning(self, "Empty Prompt", "Please describe your website in the prompt editor.")
            self.prompt_edit.setFocus()
            return

        spec = WebsiteSpec(
            name=name,
            dest_dir=dest_path,
            prompt=prompt,
            tech=tech,
            is_multipage=is_multipage,
            model=model,
        )

        # UI State transition
        self.generate_btn.setEnabled(False)
        self.name_edit.setEnabled(False)
        self.dest_edit.setEnabled(False)
        self.browse_btn.setEnabled(False)
        self.prompt_edit.setEnabled(False)
        self.radio_html.setEnabled(False)
        self.radio_react.setEnabled(False)
        self.multipage_check.setEnabled(False)
        self.progress_bar.show()
        self.status_label.show()
        self.progress_bar.setValue(5)
        self.status_label.setText("Starting website generator...")

        self.worker = WebsiteGenerationWorker(spec, self)
        self.worker.progress.connect(self._on_worker_progress)
        self.worker.finished_records.connect(lambda recs: self._on_worker_finished(spec, recs))
        self.worker.failed.connect(self._on_worker_failed)
        self.worker.start()

    def _on_worker_progress(self, msg: str, pct: int):
        self.status_label.setText(msg)
        self.progress_bar.setValue(pct)

    def _on_worker_failed(self, err_msg: str):
        self._reset_ui()
        QMessageBox.critical(self, "Generation Failed", f"Failed to generate website:\n{err_msg}")

    def _on_worker_finished(self, spec: WebsiteSpec, records: List[FileChangeRecord]):
        self._reset_ui()

        if not records:
            QMessageBox.warning(self, "No Files", "No website files were generated.")
            return

        # Open Diff Review Dialog
        diff_dialog = AgentDiffDialog(records, parent=self)
        diff_dialog.setWindowTitle(f"Review Website Files — {spec.name}")
        result = diff_dialog.exec()

        if result != QDialog.DialogCode.Accepted:
            QMessageBox.information(self, "Cancelled", "Website generation cancelled. No files were written to disk.")
            return

        # Retrieve decisions and accepted records using public API
        decisions = diff_dialog.get_decisions()
        accepted_records = [r for r in records if decisions.get(r.rel_path, False)]
        if not accepted_records:
            QMessageBox.warning(self, "No Files Selected", "All generated files were rejected. No project created.")
            return

        project_dir = (spec.dest_dir / spec.name).resolve()
        project_dir.mkdir(parents=True, exist_ok=True)

        created_count = 0
        try:
            for rec in accepted_records:
                target_file = (project_dir / rec.rel_path).resolve()
                try:
                    target_file.relative_to(project_dir)
                except ValueError:
                    raise ValueError(f"Path traversal blocked: '{rec.rel_path}' is outside project root.")

                target_file.parent.mkdir(parents=True, exist_ok=True)
                if target_file.exists():
                    backup_file = target_file.with_suffix(target_file.suffix + ".bak")
                    shutil.copy2(target_file, backup_file)

                target_file.write_text(rec.new_content or "", encoding="utf-8")
                created_count += 1
        except Exception as exc:
            QMessageBox.critical(self, "Write Error", f"Failed writing website files to disk:\n{exc}")
            return

        QMessageBox.information(
            self,
            "Website Created",
            f"Successfully created website '{spec.name}'!\n"
            f"Files created: {created_count}\n"
            f"Location: {project_dir}"
        )

        self.website_created.emit(str(project_dir))
        self.accept()

    def _reset_ui(self):
        self.generate_btn.setEnabled(True)
        self.name_edit.setEnabled(True)
        self.dest_edit.setEnabled(True)
        self.browse_btn.setEnabled(True)
        self.prompt_edit.setEnabled(True)
        self.radio_html.setEnabled(True)
        self.radio_react.setEnabled(True)
        self.multipage_check.setEnabled(True)
        self.progress_bar.hide()
        self.status_label.hide()
