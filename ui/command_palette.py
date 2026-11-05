from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QWidget,
    QLabel,
    QGraphicsDropShadowEffect,
)

from core.commands import CommandRegistry, Command


class CommandItemWidget(QWidget):
    """
    Renders a single command palette row with Category, Title, and Shortcut Badge.
    """

    def __init__(self, command: Command, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(8)

        # Title & Category
        text_layout = QHBoxLayout()
        text_layout.setSpacing(6)
        if command.category:
            cat_label = QLabel(command.category)
            cat_label.setStyleSheet("color: #79869c; font-size: 9pt; font-weight: 500;")
            text_layout.addWidget(cat_label)

            sep_label = QLabel("›")
            sep_label.setStyleSheet("color: #4a5468; font-size: 9pt;")
            text_layout.addWidget(sep_label)

        title_label = QLabel(command.title)
        title_label.setStyleSheet("color: #e4e8f0; font-size: 10pt; font-weight: 600;")
        text_layout.addWidget(title_label)
        text_layout.addStretch(1)

        layout.addLayout(text_layout, 1)

        # Shortcut badge
        if command.shortcut:
            badge = QLabel(command.shortcut)
            badge.setStyleSheet(
                "background: #2b3345; color: #a4b3cf; border: 1px solid #3d4963; "
                "border-radius: 4px; padding: 2px 7px; font-family: Consolas, monospace; font-size: 8.5pt;"
            )
            layout.addWidget(badge)


class CommandPalette(QDialog):
    """
    Borderless floating Command Palette positioned top-center of the IDE.
    """

    def __init__(self, registry: CommandRegistry, parent=None):
        super().__init__(parent)
        self.registry = registry
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(640)
        self.setMaximumHeight(420)
        self._build_ui()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(10, 10, 10, 10)

        # Outer container with border radius and dark translucent style
        self.container = QWidget()
        self.container.setObjectName("PaletteContainer")
        self.container.setStyleSheet(
            "#PaletteContainer {"
            "  background-color: #1a1d26;"
            "  border: 1px solid #333d52;"
            "  border-radius: 10px;"
            "}"
        )

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setColor(QColor(0, 0, 0, 190))
        shadow.setOffset(0, 8)
        self.container.setGraphicsEffect(shadow)

        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(10, 10, 10, 10)
        container_layout.setSpacing(8)

        # Search Bar
        search_row = QHBoxLayout()
        search_row.setContentsMargins(8, 4, 8, 4)
        search_row.setSpacing(8)

        search_icon = QLabel("🔍")
        search_icon.setStyleSheet("font-size: 11pt; color: #79869c;")
        search_row.addWidget(search_icon)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type a command or search…")
        self.search_input.setStyleSheet(
            "QLineEdit {"
            "  background: transparent; color: #ffffff; border: 0;"
            "  font-size: 11pt; font-family: Segoe UI, sans-serif; padding: 4px;"
            "}"
            "QLineEdit:focus { border: 0; outline: none; }"
        )
        self.search_input.textChanged.connect(self._on_search_changed)
        self.search_input.installEventFilter(self)
        search_row.addWidget(self.search_input, 1)

        container_layout.addLayout(search_row)

        # Subtle separator
        sep = QLabel()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #272f40;")
        container_layout.addWidget(sep)

        # Command Results List
        self.results_list = QListWidget()
        self.results_list.setStyleSheet(
            "QListWidget {"
            "  background: transparent; border: 0; outline: none;"
            "}"
            "QListWidget::item {"
            "  border-radius: 6px; margin: 1px 0px;"
            "}"
            "QListWidget::item:selected {"
            "  background: #2a344a;"
            "}"
            "QListWidget::item:hover {"
            "  background: #232b3d;"
            "}"
        )
        self.results_list.itemActivated.connect(self._execute_selected)
        self.results_list.itemClicked.connect(self._execute_selected)
        container_layout.addWidget(self.results_list, 1)

        root_layout.addWidget(self.container)

    def position_top_center(self):
        parent = self.parentWidget()
        if parent:
            parent_geo = parent.geometry()
            x = parent_geo.x() + (parent_geo.width() - self.width()) // 2
            y = parent_geo.y() + 48
            self.move(max(0, x), max(0, y))

    def show_palette(self):
        self.position_top_center()
        self.search_input.clear()
        self._populate_list(self.registry.all_commands())
        self.show()
        self.raise_()
        self.activateWindow()
        self.search_input.setFocus()

    def _populate_list(self, commands: list[Command]):
        self.results_list.clear()
        for cmd in commands:
            item = QListWidgetItem(self.results_list)
            widget = CommandItemWidget(cmd)
            item.setSizeHint(widget.sizeHint())
            item.setData(Qt.ItemDataRole.UserRole, cmd)
            self.results_list.addItem(item)
            self.results_list.setItemWidget(item, widget)

        if self.results_list.count() > 0:
            self.results_list.setCurrentRow(0)

        # Dynamically adjust height
        item_count = min(8, max(2, self.results_list.count()))
        self.setFixedHeight(100 + item_count * 38)
        self.position_top_center()

    def _on_search_changed(self, text: str):
        matching = self.registry.search(text)
        self._populate_list(matching)

    def _execute_selected(self):
        item = self.results_list.currentItem()
        if not item:
            return
        cmd: Command = item.data(Qt.ItemDataRole.UserRole)
        self.close()
        if cmd and cmd.handler:
            cmd.handler()

    def eventFilter(self, obj, event):
        if obj == self.search_input and event.type() == event.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Down:
                cur = self.results_list.currentRow()
                if cur < self.results_list.count() - 1:
                    self.results_list.setCurrentRow(cur + 1)
                return True
            elif key == Qt.Key.Key_Up:
                cur = self.results_list.currentRow()
                if cur > 0:
                    self.results_list.setCurrentRow(cur - 1)
                return True
            elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._execute_selected()
                return True
            elif key == Qt.Key.Key_Escape:
                self.close()
                return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._execute_selected()
        else:
            super().keyPressEvent(event)

