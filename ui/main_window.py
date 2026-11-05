import os
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Optional
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QTreeView,
    QFileDialog, QSplitter, QMessageBox, QInputDialog, QLabel,
    QPushButton, QToolBar, QStatusBar, QDialog, QProgressBar, QDialogButtonBox,
    QDockWidget, QMenu, QApplication, QTabWidget)
from PyQt6.QtGui import QKeySequence, QFileSystemModel, QShortcut, QIcon, QPixmap, QColor
from core.resources import resource_path
from core.ollama_client import OllamaClient, OllamaStreamWorker, OllamaGenerateWorker, OllamaPullWorker
from core.context_manager import ContextManager, ProjectIndexer
from core.test_generator import TestGenerator
from core.commands import CommandRegistry
from core.settings_manager import SettingsManager
from core.recovery_manager import RecoveryManager
from ui.editor_widget import EditorTabs
from ui.terminal_widget import IntegratedTerminalWidget
from ui.command_palette import CommandPalette
from ui.themes import get_theme_stylesheet
from extensions.extension_manager import ExtensionManager
from extensions.extension_registry import ExtensionRegistryClient
from ui.extensions_panel import ExtensionsPanel
from ui.git_panel import GitPanel
from core.git_service import GitService
from core.analytics_db import (
    AnalyticsDatabase, ModelUsageMetrics,
    OPERATION_CHAT, OPERATION_INLINE, OPERATION_TEST_GEN, OPERATION_AGENT, OPERATION_GIT
)
from core.project_builder import ProjectBuilder
from core.env_manager import EnvironmentManager
from ui.new_project_wizard import NewProjectWizardDialog
from ui.env_manager_dialog import EnvironmentManagerDialog
from core.website_server import WebsiteServerManager, WebsiteServerState
from core.website_generator import AIWebsiteGenerator, WebsiteSpec
from ui.website_server_panel import WebsiteServerPanel
from ui.website_builder_dialog import WebsiteBuilderDialog

class OllamaHealthWorker(QThread):
    health_checked = pyqtSignal(bool, list)

    def __init__(self, client: OllamaClient, parent=None):
        super().__init__(parent)
        self.client = client

    def run(self):
        try:
            models = self.client.list_models()
            self.health_checked.emit(True, models)
        except Exception:
            self.health_checked.emit(False, [])


class DiagnosticDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ollama setup")
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("OpenArise needs Ollama running locally and a coding model installed."))
        self.progress = QProgressBar()
        layout.addWidget(self.progress)
        self.status = QLabel("Check Ollama or install deepseek-coder.")
        layout.addWidget(self.status)
        self.pull_button = QPushButton("Install deepseek-coder")
        layout.addWidget(self.pull_button)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OpenArise IDE")
        self.resize(1500, 900)
        # Apply official infinity logo branding to window icon
        ico_path = resource_path("assets/branding/openarise.ico")
        if ico_path.exists():
            self.setWindowIcon(QIcon(str(ico_path)))
        self._apply_windows_branding()
        self.client = OllamaClient()
        self.context = ContextManager()
        self.settings_manager = SettingsManager()
        self.recovery_manager = RecoveryManager()
        self.command_registry = CommandRegistry()
        self._command_palette = None
        self.project_root = None
        self.indexer = None
        self.chat_worker = None
        self.inline_worker = None
        self.pull_worker = None
        self.chat_history = []
        self.analytics_db = AnalyticsDatabase()
        self.test_generator = TestGenerator(self.client, self)
        self.test_generator.generated.connect(self._open_generated_tests)
        self.test_generator.metrics_collected.connect(lambda m: self._record_analytics_event(OPERATION_TEST_GEN, m))
        self.test_generator.failed.connect(self._notify_error)

        # Extensions System
        catalog_path = resource_path("assets/extensions/builtin_catalog.json")
        reg_client = ExtensionRegistryClient(local_catalog_path=catalog_path if catalog_path.exists() else None)
        self.extension_manager = ExtensionManager(
            main_window=self,
            command_registry=self.command_registry,
            registry_client=reg_client,
        )
        self._build_ui()
        self._build_menus()
        self._connect_signals()
        self._install_shortcuts()
        self._register_commands()
        self.extension_manager.startup()

        # Autosave & recovery timers
        self.autosave_timer = QTimer(self)
        self.autosave_timer.timeout.connect(self._run_autosave)
        self._setup_autosave_timer()

        self.recovery_timer = QTimer(self)
        self.recovery_timer.timeout.connect(self._save_recovery_snapshot)
        self.recovery_timer.start(10000)
        self.recovery_manager.start_session(self.project_root)

        # Apply user settings (themes, editor fonts, tab size)
        self.apply_user_settings(self.settings_manager.all_settings())

        self.health_timer = QTimer(self)
        self.health_timer.timeout.connect(self.check_ollama)
        self.health_timer.start(10000)
        QTimer.singleShot(200, self.check_ollama)
        QTimer.singleShot(250, self._check_startup_recovery_and_project)

    def _apply_windows_branding(self):
        """
        Windows-specific branding:
        - Windows title bar icon (ICON_SMALL) and Windows taskbar icon (ICON_BIG)
          both use the official openarise.ico infinity branding.
        """
        if sys.platform != "win32":
            return
        try:
            import ctypes
            hwnd = int(self.winId())
            user32 = ctypes.windll.user32

            ico_path = resource_path("assets/branding/openarise.ico")
            if not ico_path.exists():
                return

            # Ensure any previous WS_EX_DLGMODALFRAME is cleared so caption icon renders
            GWL_EXSTYLE = -20
            WS_EX_DLGMODALFRAME = 0x00000001
            SWP_FRAMECHANGED = 0x0020
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_NOZORDER = 0x0004
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            if style & WS_EX_DLGMODALFRAME:
                user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style & ~WS_EX_DLGMODALFRAME)
                user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)

            IMAGE_ICON = 1
            LR_LOADFROMFILE = 0x0010
            WM_SETICON = 0x0080
            ICON_SMALL = 0
            ICON_BIG = 1
            SM_CXSMICON = 49
            SM_CYSMICON = 50
            SM_CXICON = 11
            SM_CYICON = 12

            sm_cx = user32.GetSystemMetrics(SM_CXSMICON) or 16
            sm_cy = user32.GetSystemMetrics(SM_CYSMICON) or 16
            bg_cx = user32.GetSystemMetrics(SM_CXICON) or 32
            bg_cy = user32.GetSystemMetrics(SM_CYICON) or 32

            # 1. Set ICON_SMALL for window title-bar caption
            hicon_small = user32.LoadImageW(None, str(ico_path), IMAGE_ICON, sm_cx, sm_cy, LR_LOADFROMFILE)
            if hicon_small:
                user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon_small)

            # 2. Set ICON_BIG for taskbar & Alt+Tab
            hicon_big = user32.LoadImageW(None, str(ico_path), IMAGE_ICON, bg_cx, bg_cy, LR_LOADFROMFILE)
            if hicon_big:
                user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon_big)
        except Exception:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_windows_branding()

    def _build_ui(self):
        central = QWidget()
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(4, 4, 4, 4)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.fs_model = QFileSystemModel(self)
        self.fs_model.setRootPath("")
        self.tree = QTreeView()
        self.tree.setModel(self.fs_model)
        self.tree.setMinimumWidth(190)
        self.tree.setMaximumWidth(340)
        for col in range(1, 4):
            self.tree.hideColumn(col)
        self.editor = EditorTabs()
        self.chat = self._make_chat_panel()
        splitter.addWidget(self.tree)
        splitter.addWidget(self.editor)
        splitter.addWidget(self.chat)
        splitter.setSizes([240, 850, 390])
        root_layout.addWidget(splitter)
        self.setCentralWidget(central)
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        # Final minimal main toolbar: exactly 4 buttons in exact order
        for label, callback, tip in [
            ("Open Folder", self.open_project, "Open Folder (Ctrl+Shift+O)"),
            ("New File", self.new_file, "New File (Ctrl+N)"),
            ("Save", self.save_file, "Save File (Ctrl+S)"),
            ("Run Python", self.run_python, "Run Current Python File (F5)"),
        ]:
            button = QPushButton(label)
            button.setToolTip(tip)
            button.clicked.connect(callback)
            toolbar.addWidget(button)

        # Git Source Control Dock Widget on Left
        self.git_panel = GitPanel(parent=self)
        self.git_panel.ai_prompt_requested.connect(self._handle_git_ai_prompt)
        self.git_dock = QDockWidget("Source Control", self)
        self.git_dock.setObjectName("SourceControlDock")
        self.git_dock.setWidget(self.git_panel)
        self.git_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetClosable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.git_dock)
        self.git_dock.hide()

        # Extensions Dock Widget on Left
        self.extensions_panel = ExtensionsPanel(self.extension_manager, parent=self)
        self.extensions_dock = QDockWidget("Extensions", self)
        self.extensions_dock.setObjectName("ExtensionsDock")
        self.extensions_dock.setWidget(self.extensions_panel)
        self.extensions_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetClosable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.extensions_dock)
        self.extensions_dock.hide()

        # Website Server Manager & Integrated Terminal in Bottom Dock Tabs
        self.website_server_manager = WebsiteServerManager(parent=self)
        self.website_server_manager.set_dependency_approval_handler(self._request_dependency_approval)

        self.terminal = IntegratedTerminalWidget(initial_cwd=self.project_root, parent=self)
        self.website_server_panel = WebsiteServerPanel(self.website_server_manager, parent=self)
        self.website_server_panel.run_requested.connect(self.run_website)
        self.website_server_panel.fix_errors_requested.connect(self.fix_website_errors)

        self.bottom_tabs = QTabWidget()
        self.bottom_tabs.setObjectName("BottomDockTabs")
        self.bottom_tabs.setStyleSheet("""
            QTabWidget::pane { border: none; background-color: #16161a; }
            QTabBar::tab {
                background-color: #1e1e24;
                color: #9aa0a6;
                padding: 6px 14px;
                border: none;
                font-size: 10pt;
                font-weight: 500;
            }
            QTabBar::tab:selected {
                background-color: #2a2d3d;
                color: #ffffff;
                border-bottom: 2px solid #8ab4f8;
            }
        """)
        self.bottom_tabs.addTab(self.terminal, "Terminal")
        self.bottom_tabs.addTab(self.website_server_panel, "Website Server")

        self.terminal_dock = QDockWidget("Terminal / Website Server", self)
        self.terminal_dock.setObjectName("TerminalDock")
        self.terminal_dock.setWidget(self.bottom_tabs)
        self.terminal_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetClosable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.terminal_dock)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.ollama_status = QLabel("Ollama: checking…")
        self.status.addPermanentWidget(self.ollama_status)
        self.status.showMessage("Ready")

    def _make_chat_panel(self):
        from ui.chat_agent_container import ChatAgentContainer
        container = ChatAgentContainer(self.client, self.context, parent=self)
        self.agent_panel = container.agent_panel
        return container

    def _build_menus(self):
        file_menu = self.menuBar().addMenu("&File")
        for label, shortcut, callback in [
            ("Open Folder…", "Ctrl+Shift+O", self.open_project),
            ("New File", "Ctrl+N", self.new_file),
            ("Save", "Ctrl+S", self.save_file),
            ("Save All", "Ctrl+Shift+S", self.save_all_files),
            ("Go to File…", "Ctrl+P", self.go_to_file),
            ("Exit", "Ctrl+Q", self.close),
        ]:
            action = file_menu.addAction(label)
            action.setShortcut(shortcut)
            action.triggered.connect(callback)

        view_menu = self.menuBar().addMenu("&View")
        palette_act = view_menu.addAction("&Command Palette…")
        palette_act.setShortcut("Ctrl+Shift+P")
        palette_act.triggered.connect(self.show_command_palette)

        explorer_act = view_menu.addAction("Toggle &Explorer")
        explorer_act.setShortcut("Ctrl+B")
        explorer_act.triggered.connect(self.toggle_explorer)

        self.toggle_terminal_action = view_menu.addAction("&Terminal")
        self.toggle_terminal_action.setShortcut("Ctrl+`")
        self.toggle_terminal_action.triggered.connect(self.toggle_terminal)

        self.toggle_git_action = view_menu.addAction("&Source Control")
        self.toggle_git_action.setShortcut("Ctrl+Shift+G")
        self.toggle_git_action.triggered.connect(self.toggle_git_panel)

        self.toggle_extensions_action = view_menu.addAction("&Extensions")
        self.toggle_extensions_action.setShortcut("Ctrl+Shift+X")
        self.toggle_extensions_action.triggered.connect(self.toggle_extensions)

        self.toggle_agent_action = view_menu.addAction("&Agent Mode")
        self.toggle_agent_action.setShortcut("Ctrl+Shift+A")
        self.toggle_agent_action.triggered.connect(self.switch_to_agent_mode)

        self.toggle_chat_action = view_menu.addAction("&Chat Mode")
        self.toggle_chat_action.triggered.connect(self.switch_to_chat_mode)

        self.analytics_action = view_menu.addAction("&AI Usage Analytics…")
        self.analytics_action.setShortcut("Ctrl+Shift+U")
        self.analytics_action.triggered.connect(self.open_analytics)

        run_menu = self.menuBar().addMenu("&Run")
        run_action = run_menu.addAction("&Run Python File")
        run_action.setShortcut("F5")
        run_action.triggered.connect(self.run_python)

        tools_menu = self.menuBar().addMenu("&Tools")
        env_act = tools_menu.addAction("&Environment Manager…")
        env_act.setShortcut("Ctrl+Shift+E")
        env_act.triggered.connect(self.open_env_manager)
        interp_act = tools_menu.addAction("&Select Python Interpreter…")
        interp_act.triggered.connect(self.select_python_interpreter)
        reindex_act = tools_menu.addAction("&Reindex Project Files")
        reindex_act.triggered.connect(self.index_project)

        ai_menu = self.menuBar().addMenu("&AI")
        action = ai_menu.addAction("Inline Edit")
        action.setShortcut("Ctrl+K")
        action.triggered.connect(self.chat.request_inline)
        action = ai_menu.addAction("Generate Unit Tests")
        action.triggered.connect(self.generate_tests)
        find_act = ai_menu.addAction("Find in Files…")
        find_act.setShortcut("Ctrl+Shift+F")
        find_act.triggered.connect(self.find_in_files)
        ai_analytics_act = ai_menu.addAction("AI &Usage Analytics…")
        ai_analytics_act.triggered.connect(self.open_analytics)
        ai_models_act = ai_menu.addAction("&Manage AI Models…")
        ai_models_act.triggered.connect(self.open_settings)

        # Dedicated top-level Settings menu immediately before Help
        settings_menu = self.menuBar().addMenu("&Settings")
        pref_act = settings_menu.addAction("&Open Settings…")
        pref_act.setShortcut("Ctrl+,")
        pref_act.triggered.connect(self.open_settings)
        models_act = settings_menu.addAction("&Manage AI Models…")
        models_act.triggered.connect(self.open_settings)
        env_settings_act = settings_menu.addAction("&Environment Settings…")
        env_settings_act.triggered.connect(self.open_env_manager)
        ext_settings_act = settings_menu.addAction("&Manage Extensions…")
        ext_settings_act.triggered.connect(self.open_extensions)

        help_menu = self.menuBar().addMenu("&Help")
        ext_act = help_menu.addAction("&Extensions…")
        ext_act.triggered.connect(self.open_extensions)
        about_action = help_menu.addAction("&About OpenArise IDE")
        about_action.triggered.connect(self.show_about_dialog)

    def show_about_dialog(self):
        from ui.about_dialog import AboutDialog
        dialog = AboutDialog(self)
        dialog.exec()

    def _connect_signals(self):
        self.tree.doubleClicked.connect(self._open_tree_item)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_tree_context_menu)
        self.chat.refresh_button.clicked.connect(self.refresh_models)
        self.chat.send_requested.connect(self.send_chat)
        self.chat.inline_requested.connect(self.inline_edit)
        self.chat.insert_code_requested.connect(self.insert_chat_code)
        self.editor.file_changed.connect(self._on_editor_file_changed)

    def _on_editor_file_changed(self, path: str):
        self.status.showMessage(path)
        if hasattr(self, "extension_manager"):
            self.extension_manager.dispatch_file_open(path)

    def _install_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+Shift+E"), self, self.open_env_manager)
        QShortcut(QKeySequence("Ctrl+Shift+P"), self, self.show_command_palette)
        QShortcut(QKeySequence("Ctrl+Shift+A"), self, self.switch_to_agent_mode)
        QShortcut(QKeySequence("Ctrl+Shift+U"), self, self.open_analytics)
        QShortcut(QKeySequence("Ctrl+Shift+G"), self, self.toggle_git_panel)
        QShortcut(QKeySequence("Ctrl+Shift+X"), self, self.toggle_extensions)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self, self.save_all_files)
        QShortcut(QKeySequence("Ctrl+Shift+F"), self, self.find_in_files)
        QShortcut(QKeySequence("Ctrl+P"), self, self.go_to_file)
        QShortcut(QKeySequence("Ctrl+B"), self, self.toggle_explorer)
        QShortcut(QKeySequence("Ctrl+,"), self, self.open_settings)
        QShortcut(QKeySequence("Ctrl+S"), self, self.save_file)
        QShortcut(QKeySequence("Ctrl+K"), self, self.chat.request_inline)
        QShortcut(QKeySequence("Ctrl+I"), self, self.chat.request_inline)
        QShortcut(QKeySequence("Ctrl+`"), self, self.toggle_terminal)
        QShortcut(QKeySequence("F5"), self, self.run_python)
        self.rename_shortcut = QShortcut(QKeySequence("F2"), self.tree)
        self.rename_shortcut.activated.connect(self.rename_tree_item)

    def _register_commands(self):
        self.command_registry.register("file.open_folder", "Open Folder", "File", "Ctrl+Shift+O", self.open_project)
        self.command_registry.register("file.new_file", "New File", "File", "Ctrl+N", self.new_file)
        self.command_registry.register("file.save", "Save", "File", "Ctrl+S", self.save_file)
        self.command_registry.register("file.save_all", "Save All", "File", "Ctrl+Shift+S", self.save_all_files)
        self.command_registry.register("view.source_control", "Toggle Source Control", "View", "Ctrl+Shift+G", self.toggle_git_panel)
        self.command_registry.register("view.extensions", "Toggle Extensions", "View", "Ctrl+Shift+X", self.toggle_extensions)
        self.command_registry.register("run.python", "Run Python", "Run", "F5", self.run_python)
        self.command_registry.register("view.toggle_terminal", "Toggle Terminal", "View", "Ctrl+`", self.toggle_terminal)
        self.command_registry.register("terminal.clear", "Clear Terminal", "Terminal", "", self.terminal.clear_terminal)
        self.command_registry.register("ai.generate_tests", "Generate Unit Tests", "AI", "", self.generate_tests)
        self.command_registry.register("project.reindex", "Reindex Project", "Project", "", self.index_project)
        self.command_registry.register("edit.find_in_files", "Find in Files", "Edit", "Ctrl+Shift+F", self.find_in_files)
        self.command_registry.register("file.go_to_file", "Go to File", "File", "Ctrl+P", self.go_to_file)
        self.command_registry.register("view.toggle_explorer", "Toggle Explorer", "View", "Ctrl+B", self.toggle_explorer)
        self.command_registry.register("preferences.settings", "Open Settings", "Preferences", "Ctrl+,", self.open_settings)
        self.command_registry.register("help.extensions", "Open Extensions", "Help", "", self.open_extensions)
        self.command_registry.register("help.about", "About OpenArise IDE", "Help", "", self.show_about_dialog)

        # Git Commands in Command Palette
        self.command_registry.register("git.refresh", "Git: Refresh Status", "Git", "", self.git_panel.refresh_status)
        self.command_registry.register("git.stage_all", "Git: Stage All Changes", "Git", "", self.git_panel._stage_all)
        self.command_registry.register("git.unstage_all", "Git: Unstage All Changes", "Git", "", self.git_panel._unstage_all)
        self.command_registry.register("git.commit", "Git: Commit Changes", "Git", "", self.git_panel._commit)
        self.command_registry.register("git.push", "Git: Push", "Git", "", self.git_panel._push)
        self.command_registry.register("git.pull", "Git: Pull", "Git", "", self.git_panel._pull)
        self.command_registry.register("git.branches", "Git: Branches…", "Git", "", self.git_panel._show_branch_dialog)
        self.command_registry.register("git.history", "Git: History…", "Git", "", self.git_panel._show_history)
        self.command_registry.register("git.gitignore", "Git: Generate .gitignore…", "Git", "", self.git_panel._show_gitignore_dialog)
        self.command_registry.register("git.ai_commit", "AI: Generate Commit Message", "AI", "", self.git_panel._ai_generate_commit_message)

        # Agent Commands in Command Palette
        self.command_registry.register("view.chat_mode", "View: Chat Mode", "AI", "", self.switch_to_chat_mode)
        self.command_registry.register("view.agent_mode", "View: Agent Mode", "AI", "Ctrl+Shift+A", self.switch_to_agent_mode)
        self.command_registry.register("agent.start_task", "Agent: Start New Task", "AI", "", lambda: (self.switch_to_agent_mode(), hasattr(self, "agent_panel") and self.agent_panel.task_input.setFocus()))
        self.command_registry.register("agent.cancel_task", "Agent: Cancel Running Task", "AI", "", lambda: hasattr(self, "agent_panel") and self.agent_panel.cancel_task())
        self.command_registry.register("agent.rollback", "Agent: Rollback Last Task", "AI", "", lambda: hasattr(self, "agent_panel") and self.agent_panel.rollback_last_task())

        # Analytics & Model Manager Commands
        self.command_registry.register("view.ai_analytics", "View: AI Usage & Performance Analytics", "AI", "Ctrl+Shift+U", self.open_analytics)
        self.command_registry.register("ai.manage_models", "AI: Manage Local Models", "AI", "", self.open_settings)

        # Environment Manager Commands
        self.command_registry.register("tools.environment_manager", "Tools: Open Development Environment Manager", "Tools", "Ctrl+Shift+E", self.open_env_manager)
        self.command_registry.register("tools.select_interpreter", "Tools: Select Python Interpreter", "Tools", "", self.select_python_interpreter)

    def _setup_autosave_timer(self):
        enabled = self.settings_manager.get("auto_save", True)
        interval = self.settings_manager.get("auto_save_interval", 30)
        self.autosave_timer.stop()
        if enabled and interval > 0:
            self.autosave_timer.start(interval * 1000)

    def _run_autosave(self):
        if not self.settings_manager.get("auto_save", True):
            return
        results = self.editor.save_all(check_external=True)
        if results:
            saved = [path for path, ok, _ in results if ok]
            conflicts = [msg for _, ok, msg in results if not ok and "modified externally" in msg]
            if conflicts:
                self.status.showMessage(f"Auto-save: {conflicts[0]} (skipped overwrite)", 4000)
            elif saved:
                self.status.showMessage(f"Auto-saved {len(saved)} file(s) at {time.strftime('%H:%M:%S')}", 3000)

    def _save_recovery_snapshot(self):
        tabs = self.editor.get_session_tabs()
        if tabs:
            self.recovery_manager.save_snapshot(self.project_root, tabs)

    def _check_startup_recovery_and_project(self):
        # 1. Check crash recovery
        if self.recovery_manager.has_recoverable_session():
            session = self.recovery_manager.get_recovered_session()
            if session and session.get("tabs"):
                from ui.recovery_dialog import RecoveryDialog
                dialog = RecoveryDialog(session, self)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    if session.get("project_root") and Path(session["project_root"]).exists():
                        self._load_project_folder(Path(session["project_root"]))
                    self.editor.restore_session_tabs(session["tabs"])
                    self.recovery_manager.mark_recovery_handled()
                    self.status.showMessage("Restored session from crash recovery", 4000)
                else:
                    self.recovery_manager.clear_recovery()

        # 2. Check startup behavior if project not loaded
        if not self.project_root:
            behavior = self.settings_manager.get("startup_behavior", "open_last_project")
            last_root = self.settings_manager.get("last_project_root", "")
            if behavior == "open_last_project" and last_root and Path(last_root).exists():
                self._load_project_folder(Path(last_root))

    def _load_project_folder(self, folder: Path):
        self.project_root = Path(folder).resolve()
        self.context.set_project(self.project_root)
        self.fs_model.setRootPath(str(self.project_root))
        self.tree.setRootIndex(self.fs_model.index(str(self.project_root)))
        if hasattr(self, "terminal") and self.terminal:
            self.terminal.set_working_directory(self.project_root)
        if hasattr(self, "git_panel") and self.git_panel:
            self.git_panel.set_repo_root(self.project_root)
        if hasattr(self, "chat") and hasattr(self.chat, "set_project_root"):
            self.chat.set_project_root(self.project_root)
        if hasattr(self, "website_server_panel") and self.website_server_panel:
            self.website_server_panel.set_project(self.project_root)
        env_info = EnvironmentManager.detect_project_environment(self.project_root)
        venv_tag = " (.venv active)" if env_info.get("venv_exists") else ""
        self.status.showMessage(f"Project: {self.project_root}{venv_tag}")
        self.index_project()

    def show_new_project_wizard(self):
        dlg = NewProjectWizardDialog(parent=self)
        dlg.project_created.connect(lambda target_dir: self._load_project_folder(Path(target_dir)))
        dlg.exec()

    def open_env_manager(self):
        dlg = EnvironmentManagerDialog(
            project_root=self.project_root,
            settings_manager=self.settings_manager,
            parent=self,
        )
        dlg.exec()

    def select_python_interpreter(self):
        detected = EnvironmentManager.detect_python_interpreters(self.project_root)
        items = [str(p) for p in detected]
        items.append("Browse for other executable…")
        chosen, ok = QInputDialog.getItem(
            self,
            "Select Python Interpreter",
            "Select Python interpreter for current project:",
            items,
            0,
            False,
        )
        if not ok or not chosen:
            return
        if chosen == "Browse for other executable…":
            path, _ = QFileDialog.getOpenFileName(
                self, "Select Python Interpreter", "", "Python Executable (python.exe python);;All Files (*)"
            )
            if path:
                chosen = path
            else:
                return
        p = Path(chosen).resolve()
        if p.exists() and self.project_root:
            EnvironmentManager.set_project_interpreter(self.project_root, p, self.settings_manager)
            self.status.showMessage(f"Selected interpreter: {p.name}", 4000)

    def apply_user_settings(self, settings: dict):
        theme_name = settings.get("theme", "OpenArise Dark")
        css = get_theme_stylesheet(theme_name)
        self.setStyleSheet(css)
        app = QApplication.instance()
        if app:
            app.setStyleSheet(css)
        self.editor.apply_settings(settings)
        self._setup_autosave_timer()

    def save_all_files(self):
        results = self.editor.save_all(check_external=False)
        saved = [p for p, ok, _ in results if ok]
        self.status.showMessage(f"Saved {len(saved)} file(s)", 3000)

    def toggle_explorer(self):
        self.tree.setVisible(not self.tree.isVisible())

    def find_in_files(self):
        if not self.project_root:
            QMessageBox.information(self, "Find in Files", "Open a project folder first.")
            return
        query, ok = QInputDialog.getText(self, "Find in Files", "Search across project files:")
        if not ok or not query:
            return
        matches = []
        for file_path in self.project_root.rglob("*"):
            if not file_path.is_file() or file_path.suffix.lower() in (".pyc", ".git", ".ico", ".jpg", ".png", ".exe"):
                continue
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                for line_num, line in enumerate(content.splitlines(), start=1):
                    if query.lower() in line.lower():
                        rel = file_path.relative_to(self.project_root)
                        matches.append(f"{rel}:{line_num}: {line.strip()}")
            except Exception:
                continue

        self.terminal_dock.show()
        self.terminal.execute_command(f'# Find in Files: "{query}" ({len(matches)} match(es) found)')
        for m in matches[:50]:
            self.terminal.execute_command(f'# {m}')
        self.status.showMessage(f"Found {len(matches)} match(es) for '{query}'", 4000)

    def go_to_file(self):
        if not self.project_root:
            QMessageBox.information(self, "Go to File", "Open a project folder first.")
            return
        target, ok = QInputDialog.getText(self, "Go to File", "Enter filename (e.g. main.py):")
        if not ok or not target:
            return
        query = target.strip().lower()
        found = None
        for p in self.project_root.rglob("*"):
            if p.is_file() and query in p.name.lower():
                found = p
                break
        if found:
            self.editor.open_file(str(found))
            self.status.showMessage(f"Opened {found.name}", 3000)
        else:
            QMessageBox.information(self, "Go to File", f"No file matching '{target}' found.")

    def open_settings(self):
        from ui.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self.settings_manager, self.client, self)
        dlg.settings_applied.connect(self.apply_user_settings)
        dlg.exec()

    def open_analytics(self):
        from ui.analytics_dashboard import AnalyticsDashboardDialog
        dlg = AnalyticsDashboardDialog(self.analytics_db, self.client, self)
        dlg.exec()

    def _record_analytics_event(self, op_type: str, metrics_dict: dict, status: str = "success", error_msg: str = ""):
        try:
            from core.analytics_db import ModelUsageMetrics
            model = metrics_dict.get("model", "") or self.chat.current_model() or "unknown"
            metrics = ModelUsageMetrics.from_ollama_payload(
                model=model,
                operation_type=op_type,
                payload=metrics_dict,
                status=status,
                error_message=error_msg,
            )
            self.analytics_db.record_event(metrics)
        except Exception:
            pass

    def open_extensions(self):
        self.extensions_dock.show()
        self.extensions_dock.raise_()
        self.extensions_panel.search_input.setFocus()

    def toggle_extensions(self):
        visible = self.extensions_dock.isVisible()
        self.extensions_dock.setVisible(not visible)
        if not visible:
            self.extensions_dock.raise_()
            self.extensions_panel.search_input.setFocus()

    def toggle_git_panel(self):
        visible = self.git_dock.isVisible()
        self.git_dock.setVisible(not visible)
        if not visible:
            self.git_dock.raise_()
            self.git_panel.refresh_status()

    def switch_to_agent_mode(self):
        if hasattr(self, "chat") and hasattr(self.chat, "set_mode"):
            self.chat.set_mode("agent")

    def switch_to_chat_mode(self):
        if hasattr(self, "chat") and hasattr(self.chat, "set_mode"):
            self.chat.set_mode("chat")

    def _handle_git_ai_prompt(self, prompt: str):
        if hasattr(self, "chat") and self.chat:
            self.chat.input.setPlainText(prompt)
            if hasattr(self, "chat_dock") and self.chat_dock and not self.chat_dock.isVisible():
                self.chat_dock.show()
                self.chat_dock.raise_()
            self.chat.send_message()

    def open_project(self):
        folder = QFileDialog.getExistingDirectory(self, "Open Project Folder")
        if not folder:
            return
        self._load_project_folder(Path(folder))
        self.settings_manager.set("last_project_root", str(self.project_root))

    def toggle_terminal(self):
        if self.terminal_dock.isVisible() and hasattr(self, "bottom_tabs") and self.bottom_tabs.currentIndex() == 0:
            self.terminal_dock.hide()
        else:
            self.terminal_dock.show()
            self.terminal_dock.raise_()
            if hasattr(self, "bottom_tabs"):
                self.bottom_tabs.setCurrentWidget(self.terminal)
            self.terminal.focus_input()

    def show_website_server_tab(self):
        self.terminal_dock.show()
        self.terminal_dock.raise_()
        if hasattr(self, "bottom_tabs"):
            self.bottom_tabs.setCurrentWidget(self.website_server_panel)

    def index_project(self):
        if not self.project_root:
            QMessageBox.information(self, "OpenArise", "Open a project folder first.")
            return
        if self.indexer and self.indexer.isRunning():
            self.indexer.requestInterruption()
            self.indexer.wait(1500)
        self.indexer = ProjectIndexer(self.project_root, self)
        self.indexer.indexed.connect(self._index_complete)
        self.indexer.progress.connect(lambda message: self.status.showMessage(message, 1500))
        self.indexer.failed.connect(self._notify_error)
        self.indexer.start()
        self.status.showMessage("Indexing project…")

    def _index_complete(self, mapping):
        self.context.update_index(mapping)
        self.status.showMessage(f"Indexed {len(mapping)} project files", 5000)

    def _open_tree_item(self, index):
        path = self.fs_model.filePath(index)
        if Path(path).is_file():
            self.editor.open_file(path)

    def _show_tree_context_menu(self, pos):
        index = self.tree.indexAt(pos)
        target_path = Path(self.fs_model.filePath(index)).resolve() if index.isValid() else self.project_root
        if not target_path:
            return

        menu = QMenu(self)
        is_root = bool(self.project_root and target_path == self.project_root)

        if target_path.is_file():
            open_action = menu.addAction("Open")
            open_action.triggered.connect(lambda: self.editor.open_file(str(target_path)))
            menu.addSeparator()

        new_file_act = menu.addAction("New File…")
        new_file_act.triggered.connect(lambda: self.new_file_in_tree(target_path))

        new_folder_act = menu.addAction("New Folder…")
        new_folder_act.triggered.connect(lambda: self.new_folder_in_tree(target_path))

        menu.addSeparator()

        rename_act = menu.addAction("Rename…\tF2")
        rename_act.setEnabled(not is_root)
        rename_act.triggered.connect(lambda: self.rename_tree_item(target_path))

        delete_act = menu.addAction("Delete")
        delete_act.setEnabled(not is_root)
        delete_act.triggered.connect(lambda: self.delete_tree_item(target_path))

        menu.addSeparator()

        copy_path_act = menu.addAction("Copy Path")
        copy_path_act.triggered.connect(lambda: self.copy_tree_path(target_path))

        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _validate_filename(self, name: str) -> tuple[bool, str]:
        stripped = name.strip()
        if not stripped:
            return False, "Name cannot be empty."
        invalid_chars = set(r'\/:*?"<>|')
        found = [ch for ch in stripped if ch in invalid_chars]
        if found:
            return False, f"Name contains invalid character(s): {' '.join(set(found))}"
        base = stripped.split(".")[0].upper()
        if base in ("CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4",
                    "COM5", "COM6", "COM7", "COM8", "COM9", "LPT1", "LPT2",
                    "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"):
            return False, f"'{base}' is a reserved Windows filename."
        return True, ""

    def _resolve_target_dir(self, target_path):
        if target_path is None or not isinstance(target_path, (Path, str)):
            index = self.tree.currentIndex()
            target_path = Path(self.fs_model.filePath(index)).resolve() if index.isValid() else self.project_root
        if not target_path:
            QMessageBox.information(self, "OpenArise", "Open a project folder first.")
            return None
        target = Path(target_path).resolve()
        return target if target.is_dir() else target.parent

    def new_file_in_tree(self, target_path=None):
        base_dir = self._resolve_target_dir(target_path)
        if not base_dir:
            return
        name, ok = QInputDialog.getText(self, "New File", f"Create new file in {base_dir.name}:")
        if not ok or not name:
            return
        valid, msg = self._validate_filename(name)
        if not valid:
            QMessageBox.warning(self, "Invalid Name", msg)
            return
        new_file = base_dir / name.strip()
        if new_file.exists():
            QMessageBox.warning(self, "File Exists", f"A file or folder named '{name}' already exists.")
            return
        try:
            new_file.touch()
            self.editor.open_file(str(new_file))
            self.status.showMessage(f"Created file: {new_file.name}", 3000)
        except OSError as exc:
            QMessageBox.critical(self, "File Creation Error", f"Cannot create file:\n{exc}")

    def new_folder_in_tree(self, target_path=None):
        base_dir = self._resolve_target_dir(target_path)
        if not base_dir:
            return
        name, ok = QInputDialog.getText(self, "New Folder", f"Create new folder in {base_dir.name}:")
        if not ok or not name:
            return
        valid, msg = self._validate_filename(name)
        if not valid:
            QMessageBox.warning(self, "Invalid Name", msg)
            return
        new_folder = base_dir / name.strip()
        if new_folder.exists():
            QMessageBox.warning(self, "Folder Exists", f"A folder or file named '{name}' already exists.")
            return
        try:
            new_folder.mkdir(parents=False, exist_ok=False)
            self.status.showMessage(f"Created folder: {new_folder.name}", 3000)
        except OSError as exc:
            QMessageBox.critical(self, "Folder Creation Error", f"Cannot create folder:\n{exc}")

    def rename_tree_item(self, target_path=None):
        if target_path is None or not isinstance(target_path, (Path, str)):
            index = self.tree.currentIndex()
            if not index.isValid():
                return
            target_path = Path(self.fs_model.filePath(index)).resolve()
        else:
            target_path = Path(target_path).resolve()

        if self.project_root and target_path == self.project_root:
            QMessageBox.warning(self, "Rename Protected", "Cannot rename the project root directory.")
            return

        new_name, ok = QInputDialog.getText(
            self, "Rename", f"Rename '{target_path.name}' to:", text=target_path.name
        )
        if not ok or not new_name or new_name.strip() == target_path.name:
            return
        valid, msg = self._validate_filename(new_name)
        if not valid:
            QMessageBox.warning(self, "Invalid Name", msg)
            return

        new_path = target_path.parent / new_name.strip()
        if new_path.exists() and new_path != target_path:
            QMessageBox.warning(self, "Rename Error", f"An item named '{new_name}' already exists.")
            return

        try:
            target_path.rename(new_path)
            self.editor.update_file_path(target_path, new_path)
            self.status.showMessage(f"Renamed {target_path.name} to {new_path.name}", 3000)
        except OSError as exc:
            QMessageBox.critical(self, "Rename Failed", f"Cannot rename item:\n{exc}")

    def delete_tree_item(self, target_path=None):
        if target_path is None or not isinstance(target_path, (Path, str)):
            index = self.tree.currentIndex()
            if not index.isValid():
                return
            target_path = Path(self.fs_model.filePath(index)).resolve()
        else:
            target_path = Path(target_path).resolve()

        if self.project_root and target_path == self.project_root:
            QMessageBox.warning(self, "Delete Protected", "Cannot delete the project root directory.")
            return

        is_open = self.editor.is_file_open(target_path) or self.editor.is_path_under_open_tab(target_path)
        if is_open:
            confirm = QMessageBox.warning(
                self,
                "Delete Open File",
                f"'{target_path.name}' is currently open in the editor.\nAre you sure you want to permanently delete it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
        else:
            confirm = QMessageBox.question(
                self,
                "Confirm Delete",
                f"Are you sure you want to delete '{target_path.name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            self.editor.close_tab_by_path(target_path)
            if target_path.is_dir():
                shutil.rmtree(target_path)
            else:
                target_path.unlink()
            self.status.showMessage(f"Deleted {target_path.name}", 3000)
        except OSError as exc:
            QMessageBox.critical(self, "Delete Failed", f"Cannot delete item:\n{exc}")

    def copy_tree_path(self, target_path=None):
        if target_path is None or not isinstance(target_path, (Path, str)):
            index = self.tree.currentIndex()
            if not index.isValid():
                return
            target_path = Path(self.fs_model.filePath(index)).resolve()
        else:
            target_path = Path(target_path).resolve()
        resolved = str(target_path)
        QApplication.clipboard().setText(resolved)
        self.status.showMessage(f"Copied: {resolved}", 3000)

    def run_python(self):
        editor = self.editor.current_editor()
        if not editor or not editor.property("file_path"):
            QMessageBox.information(self, "Run Python", "Open and save a Python file to run.")
            return

        file_path = Path(editor.property("file_path")).resolve()
        if editor.document().isModified():
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                f"'{file_path.name}' has unsaved changes.\nSave changes before running?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save
            )
            if reply == QMessageBox.StandardButton.Cancel:
                return
            self.editor.save_current()

        # Resolve Python interpreter (project configured -> project .venv -> app .venv -> sys.executable)
        python_exe = EnvironmentManager.get_project_interpreter(self.project_root, self.settings_manager)

        # Show terminal dock and focus
        self.terminal_dock.show()
        self.terminal_dock.raise_()

        # Execute in terminal
        if self.terminal.shell_type == "PowerShell":
            cmd = f'& "{python_exe}" "{file_path}"'
        else:
            cmd = f'"{python_exe}" "{file_path}"'

        self.terminal.execute_command(cmd)
        self.status.showMessage(f"Running {file_path.name}…", 4000)

    def new_file(self):
        self.editor.new_file()

    def save_file(self):
        path = self.editor.save_current()
        if path:
            self.status.showMessage(f"Saved {path}", 3000)
            if hasattr(self, "extension_manager"):
                self.extension_manager.dispatch_file_save(path)
            if hasattr(self, "git_panel") and self.git_panel:
                self.git_panel.refresh_status()

    def get_active_file_context(self) -> Optional[dict]:
        """
        Retrieves active editor information and current buffer content (including unsaved edits).
        Returns None if no editor tab is active.
        """
        editor = self.editor.current_editor()
        if not editor:
            return None

        file_path_str = editor.property("file_path")
        current_idx = self.editor.currentIndex()
        tab_title = self.editor.tabText(current_idx) if current_idx >= 0 else "untitled"

        if file_path_str:
            p = Path(file_path_str)
            filename = p.name
            if self.project_root:
                try:
                    rel_path = str(p.resolve().relative_to(self.project_root.resolve()))
                except ValueError:
                    rel_path = str(p)
            else:
                rel_path = str(p)
        else:
            filename = tab_title
            rel_path = tab_title

        # Live editor buffer content (including any unsaved edits)
        content = editor.toPlainText()
        is_unsaved = editor.document().isModified()

        # Sensible context-size limit for large files (50,000 chars, ~1500 lines)
        max_active_chars = 50_000
        truncated = False
        if len(content) > max_active_chars:
            content = content[:max_active_chars] + f"\n\n[... Truncated {len(content) - max_active_chars} characters to fit context budget ...]"
            truncated = True

        return {
            "editor": editor,
            "filename": filename,
            "path": rel_path,
            "content": content,
            "is_unsaved": is_unsaved,
            "truncated": truncated,
            "abs_path": file_path_str,
        }

    def _active_file_relative(self):
        ctx = self.get_active_file_context()
        return ctx["path"] if ctx else None

    def send_chat(self, text, model, include_codebase, attachments):
        if not model:
            self._notify_error("No Ollama model selected. Refresh models or install a coding model.")
            return

        if hasattr(self, "extension_manager"):
            text = self.extension_manager.dispatch_chat_prompt(text)

        # 1. Process active file attachment if requested
        active_ctx = None
        if "__ACTIVE__" in attachments:
            active_ctx = self.get_active_file_context()
            if not active_ctx:
                msg = "Attach active file is enabled, but no file is currently open in the editor. Please open a file or uncheck 'Attach active file'."
                self.status.showMessage("Warning: No active editor file to attach.", 5000)
                self.chat.show_error(msg)
                return

        # 2. Process explicit @file(...) attachments
        explicit_attachments = [item for item in attachments if item != "__ACTIVE__"]
        attached_files_data = {}
        for fpath in explicit_attachments:
            # Check if open in an editor tab first (preserves unsaved modifications)
            found_tab = False
            for idx in range(self.editor.count()):
                w = self.editor.widget(idx)
                if w and (w.property("file_path") == fpath or self.editor.tabText(idx) == fpath or (w.property("file_path") and Path(w.property("file_path")).name == fpath)):
                    attached_files_data[fpath] = w.toPlainText()
                    found_tab = True
                    break
            if not found_tab:
                # Read from disk
                candidate = Path(fpath)
                if not candidate.is_absolute() and self.project_root:
                    candidate = self.project_root / candidate
                if candidate.exists() and candidate.is_file():
                    try:
                        attached_files_data[fpath] = candidate.read_text(encoding="utf-8", errors="replace")
                    except Exception as exc:
                        self.chat.show_error(f"Cannot read attached file '{fpath}': {exc}")
                        return
                else:
                    self.chat.show_error(f"Cannot find attached file '{fpath}'.")
                    return

        selected = self.editor.selection_text()

        # 3. Assemble prompt with clear untrusted source code delimiters
        prompt_parts = [
            "You are OpenArise, a careful and expert local software engineering assistant.",
            "Adhere strictly to the following instructions:",
            "1. Base your answer directly on the attached source files and project context provided below.",
            "2. Never hallucinate, invent, or assume functions or logic that are not present in the provided source code.",
            "3. If an attached file is provided, inspect its exact code to answer questions about functions, classes, or logic.",
            "4. If context is insufficient to answer the question, state clearly what is missing rather than inventing details.",
            "5. Format your response cleanly using Markdown headings, bullet lists, and fenced code blocks.\n"
        ]

        context_blocks = []
        if active_ctx:
            status_desc = "Modified (unsaved in editor)" if active_ctx["is_unsaved"] else "Saved on disk"
            context_blocks.append(
                f"[ATTACHED ACTIVE FILE: {active_ctx['filename']}]\n"
                f"Path: {active_ctx['path']}\n"
                f"Status: {status_desc}\n"
                f"--- BEGIN {active_ctx['filename']} ---\n"
                f"{active_ctx['content']}\n"
                f"--- END {active_ctx['filename']} ---"
            )
        else:
            context_blocks.append("[ACTIVE FILE: None attached]")

        for rel, content in attached_files_data.items():
            context_blocks.append(
                f"[ATTACHED FILE: {rel}]\n"
                f"--- BEGIN {rel} ---\n"
                f"{content}\n"
                f"--- END {rel} ---"
            )

        if selected:
            context_blocks.append(f"[SELECTED CODE IN EDITOR]:\n{selected}")

        if include_codebase:
            cb_chunks = []
            for relative, content in self.context.files.items():
                if active_ctx and relative == active_ctx["path"]:
                    continue
                cb_chunks.append(f"PROJECT FILE: {relative}\n{content[:4000]}")
            if cb_chunks:
                context_blocks.append("[PROJECT CODEBASE CONTEXT]:\n" + "\n\n".join(cb_chunks))

        prompt_parts.append("==================== PROJECT CONTEXT ====================")
        prompt_parts.append("\n\n".join(context_blocks))
        prompt_parts.append("==================== END CONTEXT ====================\n")
        prompt_parts.append(f"USER REQUEST:\n{text}")

        prompt = "\n".join(prompt_parts)

        # 4. Multi-turn chat history
        if not hasattr(self, "chat_history"):
            self.chat_history = []

        user_message = {"role": "user", "content": prompt}
        messages_to_send = self.chat_history + [user_message]

        self.chat.append_user(text)
        self.chat.begin_response()

        if self.chat_worker and self.chat_worker.isRunning():
            self.chat_worker.cancel()
            self.chat_worker.requestInterruption()
            self.chat_worker.wait(1000)

        self.chat_worker = OllamaStreamWorker(self.client, model, messages_to_send, self)
        self.chat_worker.token.connect(self.chat.append_token)

        def _on_chat_finished(full_text):
            self.chat.finish_response()
            self.chat_history.append(user_message)
            self.chat_history.append({"role": "assistant", "content": full_text})
            # Bound history to last 16 messages to prevent unbounded context growth
            if len(self.chat_history) > 16:
                self.chat_history = self.chat_history[-16:]

        self.chat_worker.finished_text.connect(_on_chat_finished)
        self.chat_worker.metrics_collected.connect(lambda m: self._record_analytics_event(OPERATION_CHAT, m))
        self.chat_worker.failed.connect(lambda err: (
            self._record_analytics_event(OPERATION_CHAT, {"model": model}, status="failed", error_msg=err),
            self._chat_failed(err)
        ))
        self.chat_worker.start()

    def inline_edit(self, instruction):
        editor = self.editor.current_editor()
        if not editor:
            self._notify_error("Open a file before using Inline Edit.")
            return
        cursor = editor.textCursor()
        selected = cursor.selectedText().replace("\u2029", "\n")
        if not selected:
            self._notify_error("Select the code you want the AI to edit.")
            return
        model = self.chat.current_model()
        if not model:
            self._notify_error("No Ollama model is selected.")
            return
        prompt = (
            "Rewrite the selected code according to the instruction. Return only replacement code, "
            "without markdown fences or explanations.\n\n"
            f"Instruction: {instruction}\n\nSelected code:\n{selected}"
        )
        self.chat.begin_response()
        if self.inline_worker and self.inline_worker.isRunning():
            self.inline_worker.cancel()
            self.inline_worker.requestInterruption()
            self.inline_worker.wait(1000)
        self.inline_worker = OllamaGenerateWorker(self.client, model, prompt, self)
        self.inline_worker.token.connect(self.chat.append_token)
        self.inline_worker.metrics_collected.connect(lambda m: self._record_analytics_event(OPERATION_INLINE, m))
        self.inline_worker.finished_text.connect(self._apply_inline_result)
        self.inline_worker.failed.connect(lambda err: (self._record_analytics_event(OPERATION_INLINE, {"model": model}, status="failed", error_msg=err), self._chat_failed(err)))
        self.inline_worker.start()

    def _apply_inline_result(self, text):
        self.chat.finish_response()
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            lines = lines[1:-1] if len(lines) > 1 and lines[-1].strip() == "```" else lines[1:]
            cleaned = "\n".join(lines)
        self.editor.apply_inline_result(cleaned)

    def insert_chat_code(self, code, replace_selection):
        editor = self.editor.current_editor()
        if editor:
            cursor = editor.textCursor()
            if not replace_selection and cursor.hasSelection():
                cursor.clearSelection()
            cursor.insertText(code)

    def generate_tests(self):
        editor = self.editor.current_editor()
        if not editor:
            self._notify_error("Open a source file before generating tests.")
            return
        path = editor.property("file_path")
        if not path:
            self._notify_error("Save the source file before generating tests.")
            return
        model = self.chat.current_model()
        if not model:
            self._notify_error("No Ollama model is selected.")
            return
        self.test_generator.generate(model, path, editor.toPlainText(), self.editor.selection_text())
        self.status.showMessage("Generating unit tests…")

    def _open_generated_tests(self, path, _content):
        self.editor.open_file(path)
        self.status.showMessage(f"Generated tests: {path}", 5000)

    @property
    def command_palette(self):
        if getattr(self, "_command_palette", None) is None:
            self._command_palette = CommandPalette(self.command_registry, self)
        return self._command_palette

    @command_palette.setter
    def command_palette(self, val):
        self._command_palette = val

    def show_command_palette(self):
        self.command_palette.show_palette()

    def check_ollama(self):
        if getattr(self, "_is_closed", False):
            return
        if hasattr(self, "_health_worker") and self._health_worker and self._health_worker.isRunning():
            return
        self._health_worker = OllamaHealthWorker(self.client)
        self._health_worker.health_checked.connect(self._on_ollama_health_result)
        self._health_worker.start()

    def _on_ollama_health_result(self, connected: bool, models: list):
        if getattr(self, "_is_closed", False):
            return
        if connected:
            self.ollama_status.setText("● Ollama Connected")
            self.ollama_status.setStyleSheet("color:#65d98b")
            self.chat.set_models(models)
            if not any(name.split(":")[0] in ("deepseek-coder", "qwen2.5-coder") for name in models):
                self.status.showMessage("Install a coding model from the Ollama setup dialog.", 5000)
        else:
            self.ollama_status.setText("● Ollama Offline")
            self.ollama_status.setStyleSheet("color:#ff6b6b")
            self._show_diagnostic()

    def refresh_models(self):
        self.check_ollama()
        self.status.showMessage("Refreshing model list…", 2000)

    def _show_diagnostic(self):
        if getattr(self, "_diagnostic_open", False):
            return
        dialog = DiagnosticDialog(self)
        self._diagnostic_open = True
        dialog.pull_button.clicked.connect(lambda: self._pull_model(dialog))
        dialog.finished.connect(lambda _: setattr(self, "_diagnostic_open", False))
        dialog.show()

    def _pull_model(self, dialog):
        if self.pull_worker and self.pull_worker.isRunning():
            return
        dialog.pull_button.setEnabled(False)
        dialog.status.setText("Downloading deepseek-coder…")
        self.pull_worker = OllamaPullWorker(self.client, "deepseek-coder", self)
        self.pull_worker.progress.connect(lambda status, percent: (dialog.status.setText(status), dialog.progress.setValue(percent)))
        self.pull_worker.completed.connect(lambda: (dialog.status.setText("Model installed."), dialog.progress.setValue(100), dialog.pull_button.setEnabled(True), self.refresh_models()))
        self.pull_worker.failed.connect(lambda message: (dialog.status.setText(message), dialog.pull_button.setEnabled(True)))
        self.pull_worker.start()

    def _chat_failed(self, message):
        self.chat.show_error(message)
        self.status.showMessage("AI request failed", 4000)

    def _notify_error(self, message):
        QMessageBox.warning(self, "OpenArise IDE", str(message))

    def show_website_builder(self):
        from ui.website_builder_dialog import WebsiteBuilderDialog
        active_model = self.chat.current_model() or "qwen2.5-coder:7b"
        initial_dest = self.project_root.parent if self.project_root else None
        dialog = WebsiteBuilderDialog(default_model=active_model, initial_dest=initial_dest, parent=self)
        dialog.website_created.connect(self._on_website_created)
        dialog.exec()

    def _on_website_created(self, project_path: str):
        p = Path(project_path).resolve()
        self._load_project_folder(p)
        self.settings_manager.set("last_project_root", str(p))
        for candidate in ("index.html", "src/App.jsx", "package.json"):
            target = p / candidate
            if target.exists():
                self.editor.open_file(target)
                break
        self.show_website_server_tab()
        confirm = QMessageBox.question(
            self,
            "Run Website",
            f"Website project '{p.name}' is created!\nWould you like to start the local development server now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.run_website()

    def run_website(self):
        if not self.project_root:
            QMessageBox.information(self, "OpenArise IDE", "Please open or create a website project folder first.")
            return

        self.show_website_server_tab()
        if hasattr(self, "env_manager"):
            interp = self.env_manager.get_effective_interpreter(self.project_root)
            if interp:
                self.website_server_manager.set_interpreter(interp)

        self.website_server_manager.start(self.project_root)

    def stop_website(self):
        if hasattr(self, "website_server_manager"):
            self.website_server_manager.stop()

    def open_website_in_browser(self):
        if hasattr(self, "website_server_panel"):
            self.website_server_panel._open_browser()

    def _request_dependency_approval(self, title: str, message: str) -> bool:
        reply = QMessageBox.question(
            self,
            title,
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        return reply == QMessageBox.StandardButton.Yes

    def edit_website_with_ai(self):
        if not self.project_root:
            QMessageBox.information(self, "OpenArise IDE", "Please open a website project first.")
            return

        instruction, ok = QInputDialog.getText(
            self,
            "Edit Website with AI",
            "Describe the changes or features to add to this website:"
        )
        if not ok or not instruction.strip():
            return

        self.status.showMessage("AI Website Editor: Analyzing project and generating modifications...", 5000)
        from core.website_generator import AIWebsiteGenerator
        from ui.agent_diff_dialog import AgentDiffDialog

        model = self.chat.current_model() or "qwen2.5-coder:7b"
        try:
            records = AIWebsiteGenerator.edit_website(self.project_root, instruction.strip(), model=model)
            if not records:
                QMessageBox.information(self, "No Changes", "No modifications were proposed by the AI model.")
                return

            diff_dialog = AgentDiffDialog(records, parent=self)
            diff_dialog.setWindowTitle(f"Review Website Changes — {self.project_root.name}")
            if diff_dialog.exec() == QDialog.DialogCode.Accepted:
                decisions = diff_dialog.get_decisions()
                accepted = [r for r in records if decisions.get(r.rel_path, False)]
                applied = 0
                for rec in accepted:
                    target_file = self.project_root / rec.rel_path
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    if target_file.exists():
                        backup = target_file.with_suffix(target_file.suffix + ".bak")
                        shutil.copy2(target_file, backup)
                    target_file.write_text(rec.new_content or "", encoding="utf-8")
                    applied += 1
                self.status.showMessage(f"Applied {applied} website modification(s).", 4000)
                QMessageBox.information(self, "Website Updated", f"Successfully applied {applied} modified file(s).")
                for idx in range(self.editor.count()):
                    w = self.editor.widget(idx)
                    fp = w.property("file_path") if w else None
                    if fp and Path(fp).exists():
                        w.setPlainText(Path(fp).read_text(encoding="utf-8", errors="replace"))
                        w.document().setModified(False)
        except Exception as exc:
            QMessageBox.critical(self, "Edit Failed", f"Failed applying AI website changes:\n{exc}")

    def fix_website_errors(self, error_logs: Optional[str] = None):
        if not self.project_root:
            return
        if not error_logs:
            error_logs = "\n".join(self.website_server_manager.get_logs()[-30:])
        if not error_logs.strip():
            QMessageBox.information(self, "No Errors", "No error logs were found to diagnose.")
            return

        self.status.showMessage("AI Error Diagnostics: Proposing code fix...", 5000)
        from core.website_generator import AIWebsiteGenerator
        from ui.agent_diff_dialog import AgentDiffDialog

        model = self.chat.current_model() or "qwen2.5-coder:7b"
        try:
            records = AIWebsiteGenerator.fix_website_errors(self.project_root, error_logs, model=model)
            if not records:
                QMessageBox.information(self, "No Fix Found", "AI could not propose an automated fix for this error.")
                return

            diff_dialog = AgentDiffDialog(records, parent=self)
            diff_dialog.setWindowTitle(f"Review AI Bugfix — {self.project_root.name}")
            if diff_dialog.exec() == QDialog.DialogCode.Accepted:
                decisions = diff_dialog.get_decisions()
                accepted = [r for r in records if decisions.get(r.rel_path, False)]
                for rec in accepted:
                    target_file = self.project_root / rec.rel_path
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    target_file.write_text(rec.new_content or "", encoding="utf-8")
                QMessageBox.information(self, "Fix Applied", f"Successfully applied {len(accepted)} fixed file(s).")
        except Exception as exc:
            QMessageBox.critical(self, "Fix Failed", f"Error applying fix:\n{exc}")

    def closeEvent(self, event):
        self._is_closed = True
        if hasattr(self, "website_server_manager") and self.website_server_manager:
            self.website_server_manager.stop()
        if hasattr(self, "health_timer") and self.health_timer.isActive():
            self.health_timer.stop()
        if hasattr(self, "autosave_timer") and self.autosave_timer.isActive():
            self.autosave_timer.stop()
        if hasattr(self, "recovery_timer") and self.recovery_timer.isActive():
            self.recovery_timer.stop()
        if hasattr(self, "_health_worker") and self._health_worker and self._health_worker.isRunning():
            self._health_worker.wait(1000)
        if hasattr(self, "settings_manager"):
            if self.project_root:
                self.settings_manager.set("last_project_root", str(self.project_root))
            else:
                self.settings_manager.set("last_project_root", "")
        if hasattr(self, "recovery_manager"):
            self.recovery_manager.mark_clean_exit()
        if hasattr(self, "terminal") and self.terminal:
            self.terminal.shutdown()
        if hasattr(self, "agent_panel") and self.agent_panel and self.agent_panel.worker:
            if self.agent_panel.worker.isRunning():
                self.agent_panel.worker.cancel()
                self.agent_panel.worker.wait(2000)
        workers = [self.chat_worker, self.inline_worker, self.indexer, self.pull_worker,
                   getattr(self.test_generator, "worker", None),
                   getattr(self, "_health_worker", None)]
        for worker in workers:
            if worker and worker.isRunning():
                if hasattr(worker, "cancel"):
                    worker.cancel()
                worker.requestInterruption()
                worker.wait(5000)
        event.accept()
