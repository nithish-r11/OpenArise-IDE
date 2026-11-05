"""
Extension API and Context classes exposed to OpenArise IDE extensions.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from PyQt6.QtWidgets import QWidget

from extensions.models import ExtensionManifest


@dataclass
class ExtensionContext:
    """Runtime context provided to an activating extension."""
    extension_id: str
    extension_dir: Path
    storage_dir: Path
    manifest: ExtensionManifest
    subscriptions: List[Callable[[], None]] = field(default_factory=list)

    def add_disposable(self, disposable: Callable[[], None]) -> None:
        """Registers a cleanup callable executed when extension deactivates."""
        self.subscriptions.append(disposable)


class ExtensionAPI:
    """
    Public API surface provided to extension activation entry points.
    All registered resources are tracked and automatically cleaned up on deactivation.
    """

    def __init__(self, context: ExtensionContext, main_window=None, command_registry=None):
        self._context = context
        self._main_window = main_window
        self._command_registry = command_registry

        # Event callbacks
        self._file_open_listeners: List[Callable[[str], None]] = []
        self._file_save_listeners: List[Callable[[str], None]] = []
        self._chat_prompt_listeners: List[Callable[[str], Optional[str]]] = []
        self._snippets: Dict[str, Dict[str, str]] = {}

    @property
    def extension_id(self) -> str:
        return self._context.extension_id

    @property
    def manifest(self) -> ExtensionManifest:
        return self._context.manifest

    # 1. Commands & Menus
    def register_command(
        self,
        command_id: str,
        title: str,
        category: str = "Extensions",
        handler: Optional[Callable] = None,
        shortcut: str = "",
        description: str = "",
    ) -> None:
        """Registers a command into the central Command Registry and Command Palette."""
        if self._command_registry and handler:
            self._command_registry.register(
                id=command_id,
                title=title,
                category=category,
                shortcut=shortcut,
                handler=handler,
                description=description,
            )
            # Add disposal to unregister when extension is disabled
            self._context.add_disposable(lambda: self._command_registry.unregister(command_id))

    def register_menu_action(
        self,
        menu_name: str,
        action_title: str,
        handler: Callable,
        shortcut: str = "",
    ) -> None:
        """Registers an action inside an IDE menu bar item."""
        if self._main_window and hasattr(self._main_window, "menuBar"):
            menu_bar = self._main_window.menuBar()
            target_menu = None
            for action in menu_bar.actions():
                if action.text().replace("&", "").strip().lower() == menu_name.strip().lower():
                    target_menu = action.menu()
                    break

            if not target_menu:
                target_menu = menu_bar.addMenu(f"&{menu_name}")

            act = target_menu.addAction(action_title)
            if shortcut:
                act.setShortcut(shortcut)
            act.triggered.connect(handler)

            self._context.add_disposable(lambda: target_menu.removeAction(act))

    # 2. Sidebar & Views
    def register_sidebar_panel(self, panel_id: str, title: str, widget: QWidget, icon=None) -> None:
        """Registers a custom dock panel or widget in the IDE."""
        if self._main_window and hasattr(self._main_window, "addDockWidget"):
            from PyQt6.QtWidgets import QDockWidget
            from PyQt6.QtCore import Qt

            dock = QDockWidget(title, self._main_window)
            dock.setObjectName(f"ExtensionDock_{panel_id}")
            dock.setWidget(widget)
            if icon:
                dock.setWindowIcon(icon)
            self._main_window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
            self._context.add_disposable(lambda: (self._main_window.removeDockWidget(dock), dock.deleteLater()))

    # 3. Themes & Styling
    def register_theme(self, theme_name: str, stylesheet_css: str) -> None:
        """Registers a new theme stylesheet accessible in Settings."""
        from ui.themes import THEMES
        THEMES[theme_name] = stylesheet_css
        self._context.add_disposable(lambda: THEMES.pop(theme_name, None))

    # 4. Snippets
    def register_snippet(self, prefix: str, body: str, description: str = "") -> None:
        """Registers a code snippet."""
        self._snippets[prefix] = {"body": body, "description": description}
        self._context.add_disposable(lambda: self._snippets.pop(prefix, None))

    def get_snippets(self) -> Dict[str, Dict[str, str]]:
        return dict(self._snippets)

    # 5. Lifecycle event listeners
    def on_file_open(self, callback: Callable[[str], None]) -> None:
        self._file_open_listeners.append(callback)
        self._context.add_disposable(lambda: self._file_open_listeners.remove(callback) if callback in self._file_open_listeners else None)

    def on_file_save(self, callback: Callable[[str], None]) -> None:
        self._file_save_listeners.append(callback)
        self._context.add_disposable(lambda: self._file_save_listeners.remove(callback) if callback in self._file_save_listeners else None)

    def on_chat_prompt(self, callback: Callable[[str], Optional[str]]) -> None:
        self._chat_prompt_listeners.append(callback)
        self._context.add_disposable(lambda: self._chat_prompt_listeners.remove(callback) if callback in self._chat_prompt_listeners else None)

    # Dispatch helpers called by MainWindow / ExtensionManager
    def dispatch_file_open(self, path: str) -> None:
        for listener in list(self._file_open_listeners):
            try:
                listener(path)
            except Exception:
                pass

    def dispatch_file_save(self, path: str) -> None:
        for listener in list(self._file_save_listeners):
            try:
                listener(path)
            except Exception:
                pass

    def dispatch_chat_prompt(self, prompt: str) -> str:
        current_prompt = prompt
        for listener in list(self._chat_prompt_listeners):
            try:
                result = listener(current_prompt)
                if isinstance(result, str):
                    current_prompt = result
            except Exception:
                pass
        return current_prompt

    # 6. IDE Editor & Terminal interaction helpers
    def get_active_editor_text(self) -> str:
        if self._main_window and hasattr(self._main_window, "editor"):
            ed = self._main_window.editor.current_editor()
            if ed:
                return ed.toPlainText()
        return ""

    def set_active_editor_text(self, text: str) -> None:
        if self._main_window and hasattr(self._main_window, "editor"):
            ed = self._main_window.editor.current_editor()
            if ed:
                ed.setPlainText(text)

    def insert_text_at_cursor(self, text: str) -> None:
        if self._main_window and hasattr(self._main_window, "editor"):
            ed = self._main_window.editor.current_editor()
            if ed:
                ed.insertPlainText(text)

    def execute_terminal_command(self, command: str) -> None:
        if self._main_window and hasattr(self._main_window, "terminal"):
            self._main_window.terminal.execute_command(command)

    def send_chat_message(self, prompt: str) -> None:
        if self._main_window and hasattr(self._main_window, "chat"):
            self._main_window.chat.input.setPlainText(prompt)
            self._main_window.chat._on_send_clicked()

