import os
import re
from pathlib import Path
from PyQt6.QtCore import Qt, QRect, QSize, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QTextFormat, QFont, QSyntaxHighlighter, QTextCharFormat
from PyQt6.QtWidgets import QWidget, QPlainTextEdit, QTextEdit, QTabWidget, QVBoxLayout, QInputDialog, QMessageBox

class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.rules = []
        keyword = QTextCharFormat()
        keyword.setForeground(QColor("#c792ea"))
        keyword.setFontWeight(QFont.Weight.Bold)
        for word in "and as assert async await break class continue def del elif else except False finally for from global if import in is lambda None nonlocal not or pass raise return True try while with yield".split():
            self.rules.append((re.compile(rf"\b{word}\b"), keyword))
        string = QTextCharFormat()
        string.setForeground(QColor("#c3e88d"))
        self.rules.extend([(re.compile(r'"[^"\n]*"'), string), (re.compile(r"'[^'\n]*'"), string)])
        comment = QTextCharFormat()
        comment.setForeground(QColor("#697386"))
        self.rules.append((re.compile(r"#[^\n]*"), comment))
        number = QTextCharFormat()
        number.setForeground(QColor("#f78c6c"))
        self.rules.append((re.compile(r"\b[0-9]+\b"), number))

    def highlightBlock(self, text):
        for pattern, fmt in self.rules:
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), fmt)

class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        if not getattr(self.editor, "show_line_numbers", True):
            return QSize(0, 0)
        return QSize(self.editor.line_number_width(), 0)

    def paintEvent(self, event):
        if getattr(self.editor, "show_line_numbers", True):
            self.editor.paint_line_numbers(event)

class CodeEditor(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.show_line_numbers = True
        self.tab_size = 4
        self.setFont(QFont("Consolas", 11))
        self.setTabStopDistance(4 * self.fontMetrics().horizontalAdvance(" "))
        self.line_area = LineNumberArea(self)
        self.blockCountChanged.connect(self.update_line_area_width)
        self.updateRequest.connect(self.update_line_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)
        self.highlighter = PythonHighlighter(self.document())
        self.update_line_area_width(0)
        self.setStyleSheet("QPlainTextEdit{background:#1b1e26;color:#d7dae0;border:0;selection-background-color:#344967;}")

    def apply_config(self, font_family="Consolas", font_size=11, tab_size=4, word_wrap=False, show_line_numbers=True):
        # Enforce safe positive point size fallback against QFont point size <= 0 warnings
        try:
            safe_size = int(font_size)
            if safe_size <= 0:
                safe_size = 11
        except (TypeError, ValueError):
            safe_size = 11

        safe_family = str(font_family) if font_family else "Consolas"
        font = QFont(safe_family, safe_size)
        self.setFont(font)
        self.document().setDefaultFont(font)
        self.tab_size = tab_size
        self.setTabStopDistance(tab_size * self.fontMetrics().horizontalAdvance(" "))
        self.show_line_numbers = show_line_numbers
        self.line_area.setVisible(show_line_numbers)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth if word_wrap else QPlainTextEdit.LineWrapMode.NoWrap)
        self.update_line_area_width(0)

    def line_number_width(self):
        if not self.show_line_numbers:
            return 0
        digits = len(str(max(1, self.blockCount())))
        return 14 + self.fontMetrics().horizontalAdvance("9") * digits

    def update_line_area_width(self, _):
        if self.show_line_numbers:
            self.setViewportMargins(self.line_number_width(), 0, 0, 0)
        else:
            self.setViewportMargins(0, 0, 0, 0)

    def update_line_area(self, rect, dy):
        if dy:
            self.line_area.scroll(0, dy)
        else:
            self.line_area.update(0, rect.y(), self.line_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_line_area_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        rect = self.contentsRect()
        self.line_area.setGeometry(QRect(rect.left(), rect.top(), self.line_number_width(), rect.height()))

    def paint_line_numbers(self, event):
        painter = QPainter(self.line_area)
        painter.fillRect(event.rect(), QColor("#171a21"))
        block = self.firstVisibleBlock()
        number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.setPen(QColor("#687386"))
                painter.drawText(0, top, self.line_area.width() - 7,
                                 self.fontMetrics().height(), Qt.AlignmentFlag.AlignRight, str(number + 1))
            block = block.next()
            number += 1
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())

    def highlight_current_line(self):
        selections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(QColor("#242a35"))
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            selections.append(selection)
        self.setExtraSelections(selections)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Tab and not event.modifiers():
            cursor = self.textCursor()
            if cursor.hasSelection():
                cursor.insertText("    ")
            else:
                cursor.insertText("    ")
            return
        if event.key() == Qt.Key.Key_Return:
            cursor = self.textCursor()
            block_text = cursor.block().text()
            indent = len(block_text) - len(block_text.lstrip(" "))
            if block_text.rstrip().endswith(":"):
                indent += 4
            super().keyPressEvent(event)
            self.textCursor().insertText(" " * indent)
            return
        super().keyPressEvent(event)

class EditorTabs(QTabWidget):
    inline_edit_requested = pyqtSignal(object, str)
    file_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabsClosable(True)
        self.setMovable(True)
        self.tabCloseRequested.connect(self.close_tab)
        self.currentChanged.connect(self._emit_current)
        self.config = {
            "editor_font_family": "Consolas",
            "editor_font_size": 11,
            "tab_size": 4,
            "word_wrap": False,
            "line_numbers": True,
        }

    def _config_kwargs(self):
        raw_size = self.config.get("editor_font_size", 11)
        try:
            safe_size = int(raw_size)
            if safe_size <= 0:
                safe_size = 11
        except (TypeError, ValueError):
            safe_size = 11
        return {
            "font_family": self.config.get("editor_font_family", "Consolas"),
            "font_size": safe_size,
            "tab_size": self.config.get("tab_size", 4),
            "word_wrap": self.config.get("word_wrap", False),
            "show_line_numbers": self.config.get("line_numbers", True),
        }

    def apply_settings(self, settings: dict):
        for k in self.config:
            if k in settings:
                val = settings[k]
                if k == "editor_font_size":
                    try:
                        val = int(val)
                        if val <= 0:
                            val = 11
                    except (TypeError, ValueError):
                        val = 11
                self.config[k] = val
        kwargs = self._config_kwargs()
        for index in range(self.count()):
            editor = self.widget(index)
            if isinstance(editor, CodeEditor):
                editor.apply_config(**kwargs)

    def open_file(self, path):
        path = str(Path(path).resolve())
        for index in range(self.count()):
            if self.widget(index).property("file_path") == path:
                self.setCurrentIndex(index)
                return self.widget(index)
        try:
            p = Path(path)
            content = p.read_text(encoding="utf-8", errors="replace")
            mtime = p.stat().st_mtime
        except OSError as exc:
            QMessageBox.warning(self, "OpenArise", f"Cannot open file:\n{exc}")
            return None
        editor = CodeEditor()
        editor.apply_config(**self._config_kwargs())
        editor.setPlainText(content)
        editor.setProperty("file_path", path)
        editor.setProperty("disk_mtime", mtime)
        editor.document().setModified(False)
        self.addTab(editor, p.name)
        self.setCurrentWidget(editor)
        return editor

    def new_file(self, path=None, content=""):
        editor = CodeEditor()
        editor.apply_config(**self._config_kwargs())
        editor.setPlainText(content)
        if path:
            p = Path(path).resolve()
            editor.setProperty("file_path", str(p))
            if p.exists():
                editor.setProperty("disk_mtime", p.stat().st_mtime)
        index = self.addTab(editor, Path(path).name if path else "Untitled")
        self.setCurrentIndex(index)
        return editor

    def current_editor(self):
        widget = self.currentWidget()
        return widget if isinstance(widget, CodeEditor) else None

    def save_tab(self, index: int, check_external: bool = True) -> tuple[bool, str]:
        editor = self.widget(index)
        if not isinstance(editor, CodeEditor):
            return False, "No editor"
        path = editor.property("file_path")
        if not path:
            return False, "No path assigned"
        p = Path(path)
        if check_external and p.exists():
            recorded_mtime = editor.property("disk_mtime")
            if recorded_mtime is not None:
                current_mtime = p.stat().st_mtime
                if current_mtime > recorded_mtime + 0.001:
                    return False, f"File '{p.name}' was modified externally"
        try:
            p.write_text(editor.toPlainText(), encoding="utf-8")
            editor.setProperty("disk_mtime", p.stat().st_mtime)
            editor.document().setModified(False)
            self.setTabText(index, p.name)
            return True, str(p)
        except OSError as exc:
            return False, str(exc)

    def save_current(self, check_external: bool = False):
        editor = self.current_editor()
        if editor is None:
            return None
        path = editor.property("file_path")
        if not path:
            from PyQt6.QtWidgets import QFileDialog
            path, _ = QFileDialog.getSaveFileName(self, "Save File", "", "All Files (*)")
            if not path:
                return None
            editor.setProperty("file_path", path)
        ok, msg = self.save_tab(self.currentIndex(), check_external=check_external)
        if ok:
            return path
        else:
            QMessageBox.critical(self, "Save failed", msg)
            return None

    def save_all(self, check_external: bool = True) -> list[tuple[str, bool, str]]:
        results = []
        for index in range(self.count()):
            editor = self.widget(index)
            if isinstance(editor, CodeEditor) and editor.property("file_path") and editor.document().isModified():
                ok, msg = self.save_tab(index, check_external=check_external)
                results.append((editor.property("file_path"), ok, msg))
        return results

    def get_session_tabs(self) -> list[dict]:
        tabs = []
        for index in range(self.count()):
            editor = self.widget(index)
            if isinstance(editor, CodeEditor):
                tabs.append({
                    "tab_name": self.tabText(index),
                    "file_path": editor.property("file_path"),
                    "is_modified": editor.document().isModified(),
                    "cursor_position": editor.textCursor().position(),
                    "content": editor.toPlainText(),
                })
        return tabs

    def restore_session_tabs(self, tabs: list[dict]):
        for tab in tabs:
            content = tab.get("content", "")
            path = tab.get("file_path")
            editor = CodeEditor()
            editor.apply_config(**self._config_kwargs())
            editor.setPlainText(content)
            if path:
                p = Path(path).resolve()
                editor.setProperty("file_path", str(p))
                if p.exists():
                    try:
                        editor.setProperty("disk_mtime", p.stat().st_mtime)
                    except OSError:
                        pass
            editor.document().setModified(tab.get("is_modified", False))
            cursor = editor.textCursor()
            cursor.setPosition(min(len(content), max(0, tab.get("cursor_position", 0))))
            editor.setTextCursor(cursor)
            tab_name = tab.get("tab_name") or (Path(path).name if path else "Untitled")
            idx = self.addTab(editor, tab_name)
            self.setCurrentIndex(idx)

    def close_tab(self, index):
        editor = self.widget(index)
        if editor and editor.document().isModified():
            answer = QMessageBox.question(self, "Unsaved changes",
                f"Save changes to {self.tabText(index)}?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
            if answer == QMessageBox.StandardButton.Cancel:
                return
            if answer == QMessageBox.StandardButton.Save:
                self.setCurrentIndex(index)
                if self.save_current() is None:
                    return
        self.removeTab(index)

    def _emit_current(self, _):
        editor = self.current_editor()
        if editor:
            self.file_changed.emit(editor.property("file_path") or "Untitled")

    def selection_text(self):
        editor = self.current_editor()
        return editor.textCursor().selectedText().replace("\u2029", "\n") if editor else ""

    def find_tab_by_path(self, path):
        resolved = str(Path(path).resolve())
        for index in range(self.count()):
            editor = self.widget(index)
            if editor and editor.property("file_path") == resolved:
                return index
        return None

    def is_file_open(self, path):
        return self.find_tab_by_path(path) is not None

    def is_path_under_open_tab(self, folder_path):
        resolved = str(Path(folder_path).resolve())
        for index in range(self.count()):
            editor = self.widget(index)
            tab_path = editor.property("file_path") if editor else None
            if tab_path and (tab_path == resolved or tab_path.startswith(resolved + os.sep)):
                return True
        return False

    def update_file_path(self, old_path, new_path):
        resolved_old = str(Path(old_path).resolve())
        resolved_new = str(Path(new_path).resolve())
        for index in range(self.count()):
            editor = self.widget(index)
            if not editor:
                continue
            tab_path = editor.property("file_path")
            if not tab_path:
                continue
            if tab_path == resolved_old:
                editor.setProperty("file_path", resolved_new)
                self.setTabText(index, Path(resolved_new).name)
                self.file_changed.emit(resolved_new)
            elif tab_path.startswith(resolved_old + os.sep):
                # Subpath under renamed folder
                relative = os.path.relpath(tab_path, resolved_old)
                updated_subpath = os.path.join(resolved_new, relative)
                editor.setProperty("file_path", updated_subpath)
                self.setTabText(index, Path(updated_subpath).name)

    def close_tab_by_path(self, path):
        resolved = str(Path(path).resolve())
        indices_to_close = []
        for index in range(self.count()):
            editor = self.widget(index)
            tab_path = editor.property("file_path") if editor else None
            if tab_path and (tab_path == resolved or tab_path.startswith(resolved + os.sep)):
                indices_to_close.append(index)
        for index in reversed(indices_to_close):
            self.removeTab(index)

    def apply_inline_result(self, text, replace_selection=True):
        editor = self.current_editor()
        if editor is None:
            return
        cursor = editor.textCursor()
        if replace_selection and cursor.hasSelection():
            cursor.insertText(text)
        else:
            cursor.insertText(text)
