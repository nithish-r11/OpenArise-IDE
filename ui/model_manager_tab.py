"""
AI Model Manager Settings Tab for OpenArise IDE.
Provides model discovery, metadata inspection (size, family, parameters, quantization),
default model selection, model download with streaming progress, model deletion
with confirmation, connection status checks, hardware-aware recommendations,
and navigation to the Usage Analytics Dashboard.
"""

from __future__ import annotations
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QComboBox,
    QLineEdit,
    QProgressBar,
    QFrame,
    QMessageBox,
)

from core.ollama_client import OllamaClient, OllamaPullWorker
from core.settings_manager import SettingsManager
from core.system_monitor import SystemResourceMonitor


class ModelManagerTab(QWidget):
    """
    Settings tab for managing Ollama models and viewing resource recommendations.
    """

    open_analytics_requested = pyqtSignal()
    model_changed = pyqtSignal(str)

    def __init__(
        self,
        settings_manager: SettingsManager,
        ollama_client: OllamaClient,
        parent=None
    ):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.client = ollama_client
        self.pull_worker: Optional[OllamaPullWorker] = None

        self._init_ui()
        self.refresh_models()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Connection & Recommendation Header
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        hdr_layout = QVBoxLayout(header_frame)
        hdr_layout.setContentsMargins(6, 6, 6, 6)
        hdr_layout.setSpacing(4)

        status_row = QHBoxLayout()
        self.status_indicator = QLabel("● Checking connection...")
        self.status_indicator.setStyleSheet("font-weight: bold; font-size: 12px; color: #d29922;")
        status_row.addWidget(self.status_indicator)
        status_row.addStretch()

        self.btn_refresh = QPushButton("↻ Refresh List")
        self.btn_refresh.setStyleSheet("padding: 3px 10px; font-size: 11px;")
        self.btn_refresh.clicked.connect(self.refresh_models)
        status_row.addWidget(self.btn_refresh)
        hdr_layout.addLayout(status_row)

        self.recom_lbl = QLabel("System Hardware Recommendation: Calculating...")
        self.recom_lbl.setStyleSheet("color: #58a6ff; font-size: 11px;")
        self.recom_lbl.setWordWrap(True)
        hdr_layout.addWidget(self.recom_lbl)
        layout.addWidget(header_frame)

        # Default Model Selection
        default_row = QHBoxLayout()
        def_lbl = QLabel("Default Coding Model:")
        def_lbl.setStyleSheet("font-weight: bold; color: #c9d1d9; font-size: 12px;")
        default_row.addWidget(def_lbl)

        self.default_combo = QComboBox()
        self.default_combo.setStyleSheet("background-color: #21262d; color: #c9d1d9; padding: 4px 8px;")
        self.default_combo.currentTextChanged.connect(self._on_default_model_changed)
        default_row.addWidget(self.default_combo, 1)

        btn_dashboard = QPushButton("📊 AI Analytics Dashboard")
        btn_dashboard.setStyleSheet("background-color: #1f6feb; color: #ffffff; font-weight: bold;")
        btn_dashboard.clicked.connect(self.open_analytics_requested.emit)
        default_row.addWidget(btn_dashboard)
        layout.addLayout(default_row)

        # Installed Models Table
        tbl_lbl = QLabel("Installed Local Models")
        tbl_lbl.setStyleSheet("font-weight: bold; color: #c9d1d9; font-size: 12px;")
        layout.addWidget(tbl_lbl)

        self.models_table = QTableWidget(0, 6)
        self.models_table.setHorizontalHeaderLabels([
            "Model Name", "Size", "Parameters", "Family", "Quantization", "Action"
        ])
        self.models_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.models_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.models_table, 1)

        # Download Model Section
        pull_box = QFrame()
        pull_box.setStyleSheet("background-color: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 8px;")
        pull_layout = QVBoxLayout(pull_box)
        pull_layout.setContentsMargins(6, 6, 6, 6)
        pull_layout.setSpacing(6)

        pull_input_row = QHBoxLayout()
        self.pull_input = QLineEdit()
        self.pull_input.setPlaceholderText("Enter model tag to download (e.g. qwen2.5-coder:1.5b, deepseek-coder:6.7b)...")
        pull_input_row.addWidget(self.pull_input, 1)

        self.btn_pull = QPushButton("⬇ Download Model")
        self.btn_pull.setStyleSheet("background-color: #238636; color: #ffffff; font-weight: bold;")
        self.btn_pull.clicked.connect(self._start_pull)
        pull_input_row.addWidget(self.btn_pull)
        pull_layout.addLayout(pull_input_row)

        # Progress bar
        self.pull_progress = QProgressBar()
        self.pull_progress.setFixedHeight(6)
        self.pull_progress.setRange(0, 100)
        self.pull_progress.setValue(0)
        self.pull_progress.setTextVisible(False)
        self.pull_progress.hide()
        pull_layout.addWidget(self.pull_progress)

        self.pull_status_lbl = QLabel("")
        self.pull_status_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        pull_layout.addWidget(self.pull_status_lbl)

        layout.addWidget(pull_box)

    # --- Data & Lifecycle ---

    def refresh_models(self):
        # 1. Connection check
        ok, msg = self.client.check_connection()
        if ok:
            self.status_indicator.setText(f"● {msg}")
            self.status_indicator.setStyleSheet("font-weight: bold; font-size: 12px; color: #3fb950;")
        else:
            self.status_indicator.setText(f"● Disconnected: {msg}")
            self.status_indicator.setStyleSheet("font-weight: bold; font-size: 12px; color: #f85149;")

        # 2. System Recommendations
        report = SystemResourceMonitor.inspect_system(self.client)
        if report.ram_measured:
            best_recom = next((r for r in reversed(report.recommendations) if r.suitable_for_system), None)
            recom_text = f"Hardware: {report.total_ram_gb:.1f} GB RAM ({report.available_ram_gb:.1f} GB avail). "
            if best_recom:
                recom_text += f"Recommended: {best_recom.category} ({', '.join(best_recom.suggested_models[:2])})"
            self.recom_lbl.setText(recom_text)

        # 3. Populate Models Table & Default Combo
        try:
            detailed = self.client.list_models_detailed()
        except Exception:
            detailed = []

        saved_default = self.settings_manager.get("default_ollama_model", "qwen2.5-coder:7b")
        self.default_combo.blockSignals(True)
        self.default_combo.clear()

        self.models_table.setRowCount(len(detailed))
        for row, m in enumerate(detailed):
            name = m["name"]
            self.default_combo.addItem(name)

            self.models_table.setItem(row, 0, QTableWidgetItem(name))
            self.models_table.setItem(row, 1, QTableWidgetItem(m["size_formatted"]))
            self.models_table.setItem(row, 2, QTableWidgetItem(m["parameter_size"]))
            self.models_table.setItem(row, 3, QTableWidgetItem(m["family"]))
            self.models_table.setItem(row, 4, QTableWidgetItem(m["quantization_level"]))

            # Delete button
            btn_del = QPushButton("Delete")
            btn_del.setStyleSheet("background-color: #3a1d1d; color: #f85149; border-color: #da3633; padding: 2px 8px; font-size: 11px;")
            btn_del.clicked.connect(lambda _, model_name=name: self._confirm_delete(model_name))
            self.models_table.setCellWidget(row, 5, btn_del)

        if saved_default and self.default_combo.findText(saved_default) != -1:
            self.default_combo.setCurrentText(saved_default)
        elif self.default_combo.count() > 0:
            self.default_combo.setCurrentIndex(0)
            self.settings_manager.set("default_ollama_model", self.default_combo.currentText())

        self.default_combo.blockSignals(False)

    def _on_default_model_changed(self, model_name: str):
        if model_name:
            self.settings_manager.set("default_ollama_model", model_name)
            self.model_changed.emit(model_name)

    def _confirm_delete(self, model_name: str):
        confirm = QMessageBox.question(
            self,
            "Confirm Model Removal",
            f"Are you sure you want to delete local model '{model_name}'?\n"
            "This will delete model weights from your local Ollama storage.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            ok, msg = self.client.delete_model(model_name)
            if ok:
                QMessageBox.information(self, "Model Deleted", msg)
                self.refresh_models()
            else:
                QMessageBox.warning(self, "Delete Failed", msg)

    def _start_pull(self):
        model = self.pull_input.text().strip()
        if not model:
            QMessageBox.information(self, "Model Download", "Please enter a model name to download.")
            return

        self.btn_pull.setEnabled(False)
        self.pull_progress.show()
        self.pull_progress.setValue(0)
        self.pull_status_lbl.setText(f"Connecting to Ollama to pull '{model}'...")

        self.pull_worker = OllamaPullWorker(self.client, model, parent=self)
        self.pull_worker.progress.connect(self._on_pull_progress)
        self.pull_worker.completed.connect(self._on_pull_completed)
        self.pull_worker.failed.connect(self._on_pull_failed)
        self.pull_worker.start()

    def _on_pull_progress(self, status: str, percent: int):
        self.pull_progress.setValue(percent)
        self.pull_status_lbl.setText(f"{status} ({percent}%)")

    def _on_pull_completed(self):
        self.pull_progress.hide()
        self.btn_pull.setEnabled(True)
        self.pull_status_lbl.setText("Model download completed successfully!")
        self.pull_input.clear()
        self.refresh_models()
        QMessageBox.information(self, "Download Complete", "Model downloaded successfully.")

    def _on_pull_failed(self, error: str):
        self.pull_progress.hide()
        self.btn_pull.setEnabled(True)
        self.pull_status_lbl.setText(f"Download failed: {error}")
        QMessageBox.warning(self, "Download Failed", f"Could not download model: {error}")

