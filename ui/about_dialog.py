from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QDialogButtonBox
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt

class AboutDialog(QDialog):
    """
    About dialog displaying OpenArise IDE branding, version, and architecture details.
    (Logo is not displayed in the About dialog per branding specification).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About OpenArise IDE")
        self.setFixedSize(500, 360)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(16)

        # Header with App Name and details
        title_layout = QVBoxLayout()
        title_layout.setSpacing(4)
        title = QLabel("OpenArise IDE")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff;")
        title_layout.addWidget(title)

        subtitle = QLabel("AI-Native Coding IDE")
        subtitle.setFont(QFont("Segoe UI", 11))
        subtitle.setStyleSheet("color: #8ab4f8;")
        title_layout.addWidget(subtitle)

        version = QLabel("Version 1.0.0 • Python 3.13 • PyQt6")
        version.setFont(QFont("Segoe UI", 9))
        version.setStyleSheet("color: #7a8292;")
        title_layout.addWidget(version)

        layout.addLayout(title_layout)

        # Body description
        description = QLabel(
            "OpenArise is a standalone desktop development environment combining "
            "modern code editing with local AI capabilities powered by Ollama.\n\n"
            "• Multi-tab Python code editor with syntax highlighting\n"
            "• Integrated streaming chat with local Ollama models\n"
            "• Ctrl+K inline intelligent code editing and rewriting\n"
            "• Project-wide symbol and codebase indexing\n"
            "• Automated unit test generator powered by local LLMs"
        )
        description.setFont(QFont("Segoe UI", 9))
        description.setStyleSheet(
            "color: #c9d1d9; background: #1c202a; border: 1px solid #2e3544; "
            "border-radius: 6px; padding: 12px; line-height: 1.4;"
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        # Close button
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.reject)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)

