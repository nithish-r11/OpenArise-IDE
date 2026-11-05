from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFontDatabase
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QWidget,
    QLabel,
    QComboBox,
    QSpinBox,
    QCheckBox,
    QPushButton,
    QFormLayout,
    QMessageBox,
)

from core.settings_manager import SettingsManager, VALID_THEMES, VALID_SHELLS
from core.ollama_client import OllamaClient
from ui.model_manager_tab import ModelManagerTab
from ui.env_manager_dialog import DevelopmentEnvironmentsTab


class SettingsDialog(QDialog):
    """
    Dedicated Personalization Settings Dialog.
    Allows configuring Editor, Terminal, AI Models, Themes, Startup, and Auto Save.
    """
    settings_applied = pyqtSignal(dict)

    def __init__(self, settings_manager: SettingsManager, ollama_client: OllamaClient = None, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.client = ollama_client or OllamaClient()
        self.setWindowTitle("Settings")
        self.resize(650, 520)
        self.setModal(True)
        self._build_ui()
        self.load_current_settings()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(14, 14, 14, 14)
        root_layout.setSpacing(12)

        self.tabs = QTabWidget()

        # TAB 1: Editor
        editor_tab = QWidget()
        editor_layout = QFormLayout(editor_tab)
        editor_layout.setSpacing(10)

        self.font_family_combo = QComboBox()
        # Populate monospace fonts
        families = ["Consolas", "Courier New", "Cascadia Code", "Fira Code", "Lucida Console", "Segoe UI"]
        for fam in families:
            self.font_family_combo.addItem(fam)
        editor_layout.addRow("Editor Font Family:", self.font_family_combo)

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 32)
        editor_layout.addRow("Editor Font Size:", self.font_size_spin)

        self.tab_size_spin = QSpinBox()
        self.tab_size_spin.setRange(2, 8)
        editor_layout.addRow("Tab Size (spaces):", self.tab_size_spin)

        self.line_numbers_check = QCheckBox("Show line numbers")
        editor_layout.addRow("", self.line_numbers_check)

        self.word_wrap_check = QCheckBox("Enable word wrap")
        editor_layout.addRow("", self.word_wrap_check)

        self.tabs.addTab(editor_tab, "Editor")

        # TAB 2: Appearance & Theme
        theme_tab = QWidget()
        theme_layout = QFormLayout(theme_tab)
        theme_layout.setSpacing(10)

        self.theme_combo = QComboBox()
        for t in VALID_THEMES:
            self.theme_combo.addItem(t)
        theme_layout.addRow("Color Theme:", self.theme_combo)

        theme_note = QLabel("Theme changes are applied immediately to the IDE interface.")
        theme_note.setStyleSheet("color: #79869c; font-size: 9pt;")
        theme_layout.addRow("", theme_note)

        self.tabs.addTab(theme_tab, "Appearance")

        # TAB 3: Auto Save
        autosave_tab = QWidget()
        autosave_layout = QFormLayout(autosave_tab)
        autosave_layout.setSpacing(10)

        self.autosave_check = QCheckBox("Enable Auto Save")
        autosave_layout.addRow("", self.autosave_check)

        self.autosave_interval_spin = QSpinBox()
        self.autosave_interval_spin.setRange(5, 300)
        self.autosave_interval_spin.setSuffix(" sec")
        autosave_layout.addRow("Auto Save Interval:", self.autosave_interval_spin)

        autosave_note = QLabel(
            "Auto Save only saves files with known paths and guards against "
            "overwriting files modified externally."
        )
        autosave_note.setWordWrap(True)
        autosave_note.setStyleSheet("color: #79869c; font-size: 9pt;")
        autosave_layout.addRow("", autosave_note)

        self.tabs.addTab(autosave_tab, "Auto Save")

        # TAB 4: Terminal & AI
        term_tab = QWidget()
        term_layout = QFormLayout(term_tab)
        term_layout.setSpacing(10)

        self.shell_combo = QComboBox()
        for s in VALID_SHELLS:
            self.shell_combo.addItem(s)
        term_layout.addRow("Default Terminal Shell:", self.shell_combo)

        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        for m in ("qwen2.5-coder:7b", "deepseek-coder", "codellama"):
            self.model_combo.addItem(m)
        term_layout.addRow("Default Ollama Model:", self.model_combo)

        self.startup_combo = QComboBox()
        self.startup_combo.addItem("Open Last Project", "open_last_project")
        self.startup_combo.addItem("Blank Workspace", "blank")
        term_layout.addRow("Startup Behavior:", self.startup_combo)

        self.tabs.addTab(term_tab, "Terminal")

        # TAB 5: AI & Models
        self.model_manager_tab = ModelManagerTab(self.settings_manager, self.client, self)
        self.model_manager_tab.open_analytics_requested.connect(self._open_analytics)
        self.model_manager_tab.model_changed.connect(lambda m: self.model_combo.setCurrentText(m))
        self.model_combo.currentTextChanged.connect(lambda m: self.model_manager_tab.default_combo.setCurrentText(m))
        self.tabs.addTab(self.model_manager_tab, "AI & Models")

        # TAB 6: Development Environments
        project_root = getattr(self.parent(), "project_root", None) if self.parent() else None
        self.env_manager_tab = DevelopmentEnvironmentsTab(project_root, self.settings_manager, self)
        self.tabs.addTab(self.env_manager_tab, "Development Environments")

        root_layout.addWidget(self.tabs, 1)

        # Bottom Button Bar
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.reset_btn = QPushButton("Reset to Defaults")
        self.reset_btn.clicked.connect(self._reset_defaults)
        btn_layout.addWidget(self.reset_btn)

        btn_layout.addStretch(1)

        self.apply_btn = QPushButton("Apply")
        self.apply_btn.clicked.connect(self._apply_current)
        btn_layout.addWidget(self.apply_btn)

        self.ok_btn = QPushButton("OK")
        self.ok_btn.setStyleSheet("background: #2563eb; color: #ffffff; font-weight: 600;")
        self.ok_btn.clicked.connect(self._save_and_close)
        btn_layout.addWidget(self.ok_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        root_layout.addLayout(btn_layout)

    def load_current_settings(self):
        s = self.settings_manager.all_settings()
        idx = self.font_family_combo.findText(s.get("editor_font_family", "Consolas"))
        if idx >= 0:
            self.font_family_combo.setCurrentIndex(idx)
        else:
            self.font_family_combo.setCurrentText(s.get("editor_font_family", "Consolas"))

        self.font_size_spin.setValue(s.get("editor_font_size", 11))
        self.tab_size_spin.setValue(s.get("tab_size", 4))
        self.line_numbers_check.setChecked(s.get("line_numbers", True))
        self.word_wrap_check.setChecked(s.get("word_wrap", False))

        theme_idx = self.theme_combo.findText(s.get("theme", "OpenArise Dark"))
        if theme_idx >= 0:
            self.theme_combo.setCurrentIndex(theme_idx)

        self.autosave_check.setChecked(s.get("auto_save", True))
        self.autosave_interval_spin.setValue(s.get("auto_save_interval", 30))

        shell_idx = self.shell_combo.findText(s.get("default_terminal_shell", "PowerShell"))
        if shell_idx >= 0:
            self.shell_combo.setCurrentIndex(shell_idx)

        model_idx = self.model_combo.findText(s.get("default_ollama_model", "qwen2.5-coder:7b"))
        if model_idx >= 0:
            self.model_combo.setCurrentIndex(model_idx)
        else:
            self.model_combo.setCurrentText(s.get("default_ollama_model", "qwen2.5-coder:7b"))

        start_val = s.get("startup_behavior", "open_last_project")
        for i in range(self.startup_combo.count()):
            if self.startup_combo.itemData(i) == start_val:
                self.startup_combo.setCurrentIndex(i)
                break

    def _collect_ui_settings(self) -> dict:
        return {
            "editor_font_family": self.font_family_combo.currentText(),
            "editor_font_size": self.font_size_spin.value(),
            "tab_size": self.tab_size_spin.value(),
            "line_numbers": self.line_numbers_check.isChecked(),
            "word_wrap": self.word_wrap_check.isChecked(),
            "theme": self.theme_combo.currentText(),
            "auto_save": self.autosave_check.isChecked(),
            "auto_save_interval": self.autosave_interval_spin.value(),
            "default_terminal_shell": self.shell_combo.currentText(),
            "default_ollama_model": self.model_combo.currentText(),
            "startup_behavior": self.startup_combo.currentData(),
        }

    def _apply_current(self):
        new_settings = self._collect_ui_settings()
        self.settings_manager.update(new_settings)
        self.settings_applied.emit(new_settings)

    def _save_and_close(self):
        self._apply_current()
        self.accept()

    def _open_analytics(self):
        from core.analytics_db import AnalyticsDatabase
        from ui.analytics_dashboard import AnalyticsDashboardDialog
        db = AnalyticsDatabase()
        dlg = AnalyticsDashboardDialog(db, self.client, self)
        dlg.exec()

    def _reset_defaults(self):
        confirm = QMessageBox.question(
            self,
            "Reset Settings",
            "Are you sure you want to reset all preferences to defaults?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.settings_manager.reset_to_defaults()
            self.load_current_settings()
            self.settings_applied.emit(self.settings_manager.all_settings())

