import html
import re
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTextBrowser, QTextEdit,
                             QPushButton, QComboBox, QCheckBox, QLabel, QInputDialog, QMessageBox)


def render_markdown(text: str) -> str:
    """
    Renders markdown text into clean, safe HTML formatted for OpenArise Dark.
    Supports headings, lists, tables, fenced code blocks with Pygments syntax highlighting,
    and inline code blocks. Safely entity-escapes code containing HTML.
    """
    if not text:
        return ""
    try:
        import markdown
        return markdown.markdown(
            text,
            extensions=["fenced_code", "codehilite", "tables"],
            extension_configs={
                "codehilite": {
                    "noclasses": True,
                    "pygments_style": "monokai",
                    "guess_lang": False,
                }
            }
        )
    except Exception:
        escaped = html.escape(text)
        return f"<pre style='white-space: pre-wrap; font-family: Consolas, monospace;'>{escaped}</pre>"


class ChatPanel(QWidget):
    send_requested = pyqtSignal(str, str, bool, list)
    inline_requested = pyqtSignal(str)
    insert_code_requested = pyqtSignal(str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.models = []
        self._response = ""
        self._is_streaming = False
        self._stream_start_pos = 0

        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        header.addWidget(QLabel("OpenArise AI"))
        self.model_combo = QComboBox()
        header.addWidget(self.model_combo, 1)
        self.refresh_button = QPushButton("↻")
        self.refresh_button.setToolTip("Refresh Ollama models")
        header.addWidget(self.refresh_button)
        layout.addLayout(header)

        self.output = QTextBrowser()
        self.output.setOpenExternalLinks(True)
        self.output.setStyleSheet("""
            QTextBrowser {
                background: #191d25;
                color: #d7dae0;
                border: 0;
                padding: 10px;
                font-family: 'Segoe UI', -apple-system, sans-serif;
                font-size: 10pt;
            }
            pre {
                background-color: #202631;
                color: #f8f8f2;
                border: 1px solid #2d3545;
                border-radius: 4px;
                padding: 8px;
                font-family: Consolas, 'Courier New', monospace;
                font-size: 10pt;
            }
            code {
                background-color: #252b38;
                color: #79c0ff;
                padding: 2px 4px;
                border-radius: 3px;
                font-family: Consolas, 'Courier New', monospace;
                font-size: 10pt;
            }
            h1, h2, h3, h4 {
                color: #e4e8f0;
                margin-top: 12px;
                margin-bottom: 4px;
                font-weight: 600;
            }
            ul, ol {
                margin-left: 18px;
                margin-top: 4px;
                margin-bottom: 6px;
            }
            li {
                margin-bottom: 3px;
                color: #d7dae0;
            }
        """)
        layout.addWidget(self.output, 1)

        self.action_row = QHBoxLayout()
        self.action_row.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self.action_row)

        self.codebase_check = QCheckBox("Include @codebase context")
        layout.addWidget(self.codebase_check)
        self.active_file_check = QCheckBox("Attach active file")
        self.active_file_check.setChecked(True)
        layout.addWidget(self.active_file_check)

        self.input = QTextEdit()
        self.input.setPlaceholderText("Ask OpenArise… Use @codebase or @file")
        self.input.setMaximumHeight(105)
        layout.addWidget(self.input)

        buttons = QHBoxLayout()
        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_message)
        self.inline_button = QPushButton("Inline Edit")
        self.inline_button.clicked.connect(self.request_inline)
        buttons.addWidget(self.inline_button)
        buttons.addStretch(1)
        buttons.addWidget(self.send_button)
        layout.addLayout(buttons)

    def set_models(self, models):
        if getattr(self, "models", None) == models:
            return
        self.models = list(models)
        current = self.model_combo.currentText()
        self.model_combo.clear()
        preferred = []
        for model in models:
            self.model_combo.addItem(model)
            if model.split(":")[0] in ("deepseek-coder", "qwen2.5-coder"):
                preferred.append(model)
        if current and self.model_combo.findText(current) != -1:
            self.model_combo.setCurrentText(current)
        elif preferred:
            self.model_combo.setCurrentText(preferred[0])

    def current_model(self):
        return self.model_combo.currentText()

    def append_user(self, text):
        safe = self._html(text)
        self.output.append(
            f'<div style="margin-top: 10px; margin-bottom: 8px;">'
            f'<b style="color: #8ab4f8; font-size: 11pt;">You</b>'
            f'<div style="margin-top: 3px; color: #e4e8f0; line-height: 1.4;">{safe}</div>'
            f'</div>'
        )

    def begin_response(self):
        self._response = ""
        self._is_streaming = True
        self.output.append(
            '<div style="margin-top: 12px; margin-bottom: 4px;">'
            '<b style="color: #65d98b; font-size: 11pt;">OpenArise</b>'
            '</div>'
        )
        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertBlock()
        self._stream_start_pos = cursor.position()
        self.output.setTextCursor(cursor)

    def append_token(self, token):
        if not getattr(self, "_is_streaming", False):
            return
        self._response += token
        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(token)
        self.output.setTextCursor(cursor)
        self.output.ensureCursorVisible()

    def finish_response(self):
        if not getattr(self, "_is_streaming", False):
            return
        self._is_streaming = False

        # Select the streaming text inserted since _stream_start_pos
        cursor = self.output.textCursor()
        start_pos = getattr(self, "_stream_start_pos", 0)
        cursor.setPosition(start_pos)
        cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)

        # Render full response to styled Markdown HTML
        rendered_html = render_markdown(self._response)

        # Replace streaming text with the rich Markdown HTML
        cursor.removeSelectedText()
        cursor.insertHtml(f'<div style="color: #d7dae0; font-size: 10pt; line-height: 1.45; margin-bottom: 12px;">{rendered_html}</div>')

        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.output.setTextCursor(cursor)
        self.output.ensureCursorVisible()

        # Update code action buttons WITHOUT appending duplicate code to output!
        self._add_code_actions(self._response)

    def show_error(self, message):
        safe_msg = self._html(message)
        self.output.append(
            f'<div style="margin-top: 8px; margin-bottom: 8px; color: #ff6b6b; '
            f'background: #2b181a; padding: 6px 10px; border-radius: 4px; '
            f'border: 1px solid #5a272a;"><b>Error:</b> {safe_msg}</div>'
        )

    def send_message(self):
        text = self.input.toPlainText().strip()
        if not text:
            return
        attached = re.findall(r"@file\(([^)]+)\)", text)
        include_codebase = self.codebase_check.isChecked() or "@codebase" in text
        self.input.clear()
        self.send_requested.emit(text, self.current_model(), include_codebase,
                                 attached + (["__ACTIVE__"] if self.active_file_check.isChecked() else []))

    def request_inline(self):
        text, ok = QInputDialog.getText(self, "Inline AI Edit", "Describe the requested code change:")
        if ok and text.strip():
            self.inline_requested.emit(text.strip())

    def _add_code_actions(self, response):
        while self.action_row.count():
            item = self.action_row.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        blocks = re.findall(r"```(?:[\w+-]+)?\s*\n(.*?)```", response, re.S)
        if not blocks:
            return
        code = blocks[-1]
        insert = QPushButton("Insert at Cursor")
        replace = QPushButton("Replace Selection")
        copy = QPushButton("Copy Code")
        insert.clicked.connect(lambda checked=False, value=code: self.insert_code_requested.emit(value, False))
        replace.clicked.connect(lambda checked=False, value=code: self.insert_code_requested.emit(value, True))
        copy.clicked.connect(lambda checked=False, value=code: self._copy(value))
        self.action_row.addWidget(insert)
        self.action_row.addWidget(replace)
        self.action_row.addWidget(copy)

    def _copy(self, value):
        import time
        from PyQt6.QtWidgets import QApplication
        cb = QApplication.clipboard()
        cb.setText(value)
        for _ in range(5):
            if cb.text() == value:
                break
            time.sleep(0.02)
            cb.setText(value)

    @staticmethod
    def _html(value):
        return (value.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;").replace("\n", "<br>"))
