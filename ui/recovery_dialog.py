from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QWidget,
)


class RecoveryDialog(QDialog):
    """
    Dialog displayed on startup if an unrecovered session is detected from a crash.
    Lets user choose whether to restore or discard unsaved work.
    """

    def __init__(self, session_data: dict, parent=None):
        super().__init__(parent)
        self.session_data = session_data
        self.setWindowTitle("Crash Recovery — OpenArise IDE")
        self.resize(520, 360)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        # Header info
        title_label = QLabel("Restore Unsaved Work?")
        title_label.setStyleSheet("font-size: 13pt; font-weight: bold; color: #8ab4f8;")
        layout.addWidget(title_label)

        desc_label = QLabel(
            "OpenArise IDE detected an unexpected shutdown or previous crash. "
            "The following editor tab buffers were recovered:"
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #d1d5db; font-size: 10pt;")
        layout.addWidget(desc_label)

        # List of recovered files
        self.tabs_list = QListWidget()
        self.tabs_list.setStyleSheet(
            "QListWidget { background: #12141a; border: 1px solid #282d3b; border-radius: 4px; padding: 4px; }"
            "QListWidget::item { padding: 4px 6px; }"
        )

        tabs = self.session_data.get("tabs", [])
        for tab in tabs:
            name = tab.get("tab_name", "Untitled")
            path = tab.get("file_path") or "Unsaved new file"
            mod_flag = " [Unsaved Changes]" if tab.get("is_modified") else ""
            item_text = f"📄  {name}{mod_flag}  —  {path}"
            item = QListWidgetItem(item_text)
            self.tabs_list.addItem(item)

        layout.addWidget(self.tabs_list, 1)

        note_label = QLabel(
            "Restoring will reopen these tabs and reapply unsaved text without overwriting original disk files."
        )
        note_label.setWordWrap(True)
        note_label.setStyleSheet("color: #8b949e; font-size: 9pt;")
        layout.addWidget(note_label)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.discard_btn = QPushButton("Discard Recovery")
        self.discard_btn.setStyleSheet("color: #ff8585;")
        self.discard_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.discard_btn)

        btn_layout.addStretch(1)

        self.restore_btn = QPushButton("Restore Session")
        self.restore_btn.setStyleSheet("background: #2563eb; color: #ffffff; font-weight: bold; padding: 6px 14px;")
        self.restore_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.restore_btn)

        layout.addLayout(btn_layout)

