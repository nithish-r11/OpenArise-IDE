"""
Dialog for generating .gitignore files from templates in OpenArise IDE.
"""

from pathlib import Path
from typing import List
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QCheckBox,
    QPushButton,
    QMessageBox,
    QScrollArea,
    QWidget,
)

from core.gitignore_generator import GitignoreGenerator, GITIGNORE_TEMPLATES


class GitignoreDialog(QDialog):
    """Dialog allowing users to pick templates and generate a .gitignore file."""

    def __init__(self, target_dir: Path, parent=None):
        super().__init__(parent)
        self.target_dir = Path(target_dir).resolve()
        self.setWindowTitle("Generate .gitignore — OpenArise IDE")
        self.resize(440, 380)
        self.setStyleSheet("background-color: #171920; color: #e6e8ef;")
        self.checkboxes: dict[str, QCheckBox] = {}
        self._build_ui()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(10)

        title = QLabel("📄 Generate .gitignore Templates")
        title.setStyleSheet("font-size: 11pt; font-weight: bold; color: #ffffff;")
        root_layout.addWidget(title)

        desc = QLabel(f"Select template rules to include for: <b>{self.target_dir.name}</b>")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #79869c; font-size: 9pt;")
        root_layout.addWidget(desc)

        # Template check boxes
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: #13151b; border: 1px solid #282f40; border-radius: 4px;")

        container = QWidget()
        box_layout = QVBoxLayout(container)
        box_layout.setSpacing(6)

        templates = GitignoreGenerator.list_templates()
        for t_name in templates:
            cb = QCheckBox(t_name)
            # Default check Python and General development
            if t_name in ("Python", "General development"):
                cb.setChecked(True)
            self.checkboxes[t_name] = cb
            box_layout.addWidget(cb)

        box_layout.addStretch(1)
        scroll.setWidget(container)
        root_layout.addWidget(scroll, 1)

        # Buttons
        btn_row = QHBoxLayout()
        generate_btn = QPushButton("Generate .gitignore")
        generate_btn.setStyleSheet("background: #2ea043; color: white; font-weight: bold; border-radius: 4px; padding: 6px 14px;")
        generate_btn.clicked.connect(self._generate)
        btn_row.addWidget(generate_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("background: #2a3346; color: #e6e8ef; border-radius: 4px; padding: 6px 14px;")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        root_layout.addLayout(btn_row)

    def _generate(self):
        selected = [name for name, cb in self.checkboxes.items() if cb.isChecked()]
        if not selected:
            QMessageBox.warning(self, "No Templates", "Please select at least one template.")
            return

        target_file = self.target_dir / ".gitignore"
        overwrite = False
        if target_file.exists():
            ans = QMessageBox.warning(
                self,
                "File Exists",
                "A .gitignore file already exists in this folder.\nOverwrite its contents?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ans != QMessageBox.StandardButton.Yes:
                return
            overwrite = True

        ok, msg = GitignoreGenerator.generate_gitignore(self.target_dir, selected, overwrite=overwrite)
        if ok:
            QMessageBox.information(self, "Success", msg)
            self.accept()
        else:
            QMessageBox.critical(self, "Error", msg)

