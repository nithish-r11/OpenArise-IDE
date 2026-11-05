"""
AI Usage & Performance Analytics Dashboard for OpenArise IDE.
Provides a comprehensive overview of token consumption, generation speeds,
latency, operation categories, per-model metrics, time aggregations,
hardware resource status, and CSV export.
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QWidget,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QFileDialog,
    QMessageBox,
    QFrame,
    QLineEdit,
)

from core.analytics_db import AnalyticsDatabase
from core.ollama_client import OllamaClient
from core.system_monitor import SystemResourceMonitor


class MetricCard(QFrame):
    """Reusable visual card displaying a single summary metric."""

    def __init__(self, title: str, value: str, subtext: str = "", parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        title_lbl = QLabel(title.upper())
        title_lbl.setStyleSheet("color: #8b949e; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        layout.addWidget(title_lbl)

        self.value_lbl = QLabel(value)
        self.value_lbl.setStyleSheet("color: #58a6ff; font-size: 22px; font-weight: bold;")
        layout.addWidget(self.value_lbl)

        self.subtext_lbl = QLabel(subtext)
        self.subtext_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        layout.addWidget(self.subtext_lbl)

    def update_values(self, value: str, subtext: str = ""):
        self.value_lbl.setText(value)
        if subtext:
            self.subtext_lbl.setText(subtext)


class AnalyticsDashboardDialog(QDialog):
    """
    Main Analytics Dashboard dialog.
    """

    def __init__(
        self,
        analytics_db: AnalyticsDatabase,
        ollama_client: Optional[OllamaClient] = None,
        parent=None
    ):
        super().__init__(parent)
        self.analytics_db = analytics_db
        self.ollama_client = ollama_client

        self.setWindowTitle("OpenArise AI Usage & Performance Analytics")
        self.resize(980, 680)
        self.setMinimumSize(800, 500)
        self.setStyleSheet("""
            QDialog {
                background-color: #0d1117;
                color: #c9d1d9;
                font-family: 'Segoe UI', sans-serif;
            }
            QTabWidget::pane {
                border: 1px solid #30363d;
                border-radius: 6px;
                background-color: #0d1117;
            }
            QTabBar::tab {
                background-color: #161b22;
                color: #8b949e;
                border: 1px solid #30363d;
                border-bottom: none;
                padding: 8px 16px;
                margin-right: 4px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: 500;
            }
            QTabBar::tab:selected {
                background-color: #0d1117;
                color: #58a6ff;
                font-weight: bold;
                border-bottom: 2px solid #58a6ff;
            }
            QTableWidget {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 6px;
                color: #c9d1d9;
                gridline-color: #21262d;
                font-size: 12px;
            }
            QHeaderView::section {
                background-color: #21262d;
                color: #8b949e;
                font-weight: bold;
                font-size: 11px;
                border: none;
                padding: 6px 8px;
            }
            QPushButton {
                background-color: #21262d;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 4px;
                padding: 6px 14px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #30363d;
                color: #ffffff;
            }
            QLineEdit {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 4px;
                padding: 5px 8px;
                color: #c9d1d9;
                font-size: 12px;
            }
        """)

        self._init_ui()
        self.refresh_data()

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        # Header Row
        header_row = QHBoxLayout()
        header_text = QVBoxLayout()
        title = QLabel("AI Model Usage & Performance Analytics")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffffff;")
        subtitle = QLabel("100% Local tracking of token usage, generation speeds, latencies, and system resources.")
        subtitle.setStyleSheet("color: #8b949e; font-size: 12px;")
        header_text.addWidget(title)
        header_text.addWidget(subtitle)
        header_row.addLayout(header_text)
        header_row.addStretch()

        btn_refresh = QPushButton("↻ Refresh")
        btn_refresh.clicked.connect(self.refresh_data)
        header_row.addWidget(btn_refresh)

        btn_export = QPushButton("Export CSV…")
        btn_export.clicked.connect(self._export_csv)
        header_row.addWidget(btn_export)

        btn_clear = QPushButton("Clear History")
        btn_clear.setStyleSheet("background-color: #3a1d1d; color: #f85149; border-color: #da3633;")
        btn_clear.clicked.connect(self._clear_history)
        header_row.addWidget(btn_clear)

        root_layout.addLayout(header_row)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_overview_tab(), "Overview & Hardware")
        self.tabs.addTab(self._build_time_tab(), "Time Breakdown")
        self.tabs.addTab(self._build_model_tab(), "Per-Model Usage")
        self.tabs.addTab(self._build_history_tab(), "Request History")
        root_layout.addWidget(self.tabs, 1)

    # --- Tab Builders ---

    def _build_overview_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Metric Cards Row
        cards_row = QHBoxLayout()
        self.card_requests = MetricCard("Total Requests", "0", "0 successful")
        self.card_tokens = MetricCard("Total Tokens", "0", "In: 0 | Out: 0")
        self.card_speed = MetricCard("Avg Generation Speed", "0.0 tok/s", "Valid eval metrics only")
        self.card_latency = MetricCard("Avg Response Time", "0 ms", "Avg load: 0 ms")
        cards_row.addWidget(self.card_requests)
        cards_row.addWidget(self.card_tokens)
        cards_row.addWidget(self.card_speed)
        cards_row.addWidget(self.card_latency)
        layout.addLayout(cards_row)

        # Sub-Split: Operations Table (Left) vs Hardware Resources (Right)
        split_layout = QHBoxLayout()

        # Operations Box
        ops_box = QFrame()
        ops_box.setStyleSheet("background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 10px;")
        ops_layout = QVBoxLayout(ops_box)
        ops_lbl = QLabel("Usage by Operation Category")
        ops_lbl.setStyleSheet("font-weight: bold; color: #c9d1d9; font-size: 13px;")
        ops_layout.addWidget(ops_lbl)

        self.ops_table = QTableWidget(0, 4)
        self.ops_table.setHorizontalHeaderLabels(["Operation", "Requests", "Tokens", "Avg Latency"])
        self.ops_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        ops_layout.addWidget(self.ops_table)
        split_layout.addWidget(ops_box, 3)

        # Hardware Resources Box
        hw_box = QFrame()
        hw_box.setStyleSheet("background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 10px;")
        hw_layout = QVBoxLayout(hw_box)
        hw_lbl = QLabel("Host System Resources & Memory")
        hw_lbl.setStyleSheet("font-weight: bold; color: #c9d1d9; font-size: 13px;")
        hw_layout.addWidget(hw_lbl)

        self.hw_info_lbl = QLabel("Measuring system hardware...")
        self.hw_info_lbl.setStyleSheet("font-size: 12px; color: #8b949e; line-height: 1.5;")
        self.hw_info_lbl.setWordWrap(True)
        hw_layout.addWidget(self.hw_info_lbl)
        hw_layout.addStretch()
        split_layout.addWidget(hw_box, 2)

        layout.addLayout(split_layout)
        return widget

    def _build_time_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Filter bar
        btn_row = QHBoxLayout()
        lbl = QLabel("Aggregate Interval:")
        lbl.setStyleSheet("color: #8b949e; font-size: 12px;")
        btn_row.addWidget(lbl)

        self.btn_daily = QPushButton("Daily (Last 30 Days)")
        self.btn_daily.clicked.connect(lambda: self._load_time_aggregation("daily"))
        self.btn_weekly = QPushButton("Weekly (Last 12 Weeks)")
        self.btn_weekly.clicked.connect(lambda: self._load_time_aggregation("weekly"))
        self.btn_monthly = QPushButton("Monthly (Last 12 Months)")
        self.btn_monthly.clicked.connect(lambda: self._load_time_aggregation("monthly"))

        btn_row.addWidget(self.btn_daily)
        btn_row.addWidget(self.btn_weekly)
        btn_row.addWidget(self.btn_monthly)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.time_table = QTableWidget(0, 6)
        self.time_table.setHorizontalHeaderLabels(["Period", "Requests", "Input Tokens", "Output Tokens", "Total Tokens", "Avg Speed (tok/s)"])
        self.time_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.time_table)
        return widget

    def _build_model_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        lbl = QLabel("Model Breakdown & Performance")
        lbl.setStyleSheet("font-weight: bold; color: #c9d1d9; font-size: 13px;")
        layout.addWidget(lbl)

        self.model_table = QTableWidget(0, 7)
        self.model_table.setHorizontalHeaderLabels([
            "Model Name", "Requests", "Success Rate", "Input Tokens", "Output Tokens", "Total Tokens", "Avg Speed (tok/s)"
        ])
        self.model_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.model_table)
        return widget

    def _build_history_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        filter_row = QHBoxLayout()
        search_lbl = QLabel("Search:")
        search_lbl.setStyleSheet("color: #8b949e; font-size: 12px;")
        self.history_search = QLineEdit()
        self.history_search.setPlaceholderText("Filter requests by model or operation...")
        self.history_search.textChanged.connect(self._filter_history)
        filter_row.addWidget(search_lbl)
        filter_row.addWidget(self.history_search)
        layout.addLayout(filter_row)

        self.history_table = QTableWidget(0, 8)
        self.history_table.setHorizontalHeaderLabels([
            "Timestamp", "Operation", "Model", "In Tokens", "Out Tokens", "Duration", "Speed", "Status"
        ])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.history_table)
        return widget

    # --- Data Loading ---

    def refresh_data(self):
        # 1. Update Overview Cards
        stats = self.analytics_db.get_summary_stats()
        self.card_requests.update_values(
            str(stats["total_requests"]),
            f"{stats['successful_requests']} succ, {stats['failed_requests']} fail, {stats['cancelled_requests']} canc ({stats['success_rate']}%)"
        )
        self.card_tokens.update_values(
            f"{stats['total_tokens']:,}",
            f"In: {stats['total_input_tokens']:,} | Out: {stats['total_output_tokens']:,}"
        )
        self.card_speed.update_values(
            f"{stats['avg_tokens_per_second']:.1f} tok/s",
            "Authoritative eval metrics only"
        )
        self.card_latency.update_values(
            f"{stats['avg_duration_ms']:.0f} ms",
            f"Avg model load: {stats['avg_load_duration_ms']:.0f} ms"
        )

        # 2. Update Operations Table
        ops = self.analytics_db.get_per_operation_usage()
        self.ops_table.setRowCount(len(ops))
        for row, item in enumerate(ops):
            self.ops_table.setItem(row, 0, QTableWidgetItem(str(item["operation_type"])))
            self.ops_table.setItem(row, 1, QTableWidgetItem(str(item["request_count"])))
            self.ops_table.setItem(row, 2, QTableWidgetItem(f"{item['total_tokens']:,}"))
            self.ops_table.setItem(row, 3, QTableWidgetItem(f"{round(item['avg_duration'] or 0, 1)} ms"))

        # 3. Update Hardware Resources
        report = SystemResourceMonitor.inspect_system(self.ollama_client)
        ram_tag = "[Measured]" if report.ram_measured else "[Unavailable]"
        cpu_tag = "[Measured]" if report.cpu_measured else "[Unavailable]"
        gpu_tag = "[Measured]" if report.gpu_measured else "[Unavailable]"

        vram_str = f"{report.gpu_vram_used_gb} / {report.gpu_vram_total_gb} GB" if report.gpu_measured else "Unavailable"
        loaded_str = ", ".join(m["name"] for m in report.loaded_models) if report.loaded_models else "None loaded"

        hw_text = [
            f"<b>System RAM {ram_tag}:</b> {report.used_ram_gb:.1f} / {report.total_ram_gb:.1f} GB ({report.ram_percent}% used)",
            f"<b>CPU Utilization {cpu_tag}:</b> {report.cpu_percent:.1f}%",
            f"<b>GPU Device {gpu_tag}:</b> {report.gpu_name}",
            f"<b>Dedicated VRAM {gpu_tag}:</b> {vram_str}",
            f"<b>Active Ollama Models in Memory:</b> {loaded_str}",
        ]
        self.hw_info_lbl.setText("<br>".join(hw_text))

        # 4. Update Time Aggregations (default daily)
        self._load_time_aggregation("daily")

        # 5. Update Per-Model Table
        models_data = self.analytics_db.get_per_model_usage()
        self.model_table.setRowCount(len(models_data))
        for row, item in enumerate(models_data):
            self.model_table.setItem(row, 0, QTableWidgetItem(str(item["model"])))
            self.model_table.setItem(row, 1, QTableWidgetItem(str(item["request_count"])))
            self.model_table.setItem(row, 2, QTableWidgetItem(f"{item['success_rate']}%"))
            self.model_table.setItem(row, 3, QTableWidgetItem(f"{item['input_tokens']:,}"))
            self.model_table.setItem(row, 4, QTableWidgetItem(f"{item['output_tokens']:,}"))
            self.model_table.setItem(row, 5, QTableWidgetItem(f"{item['total_tokens']:,}"))
            self.model_table.setItem(row, 6, QTableWidgetItem(f"{item['avg_speed']}"))

        # 6. Update Request History Table
        self._load_history_table()

    def _load_time_aggregation(self, interval: str):
        if interval == "weekly":
            data = self.analytics_db.get_weekly_usage(12)
        elif interval == "monthly":
            data = self.analytics_db.get_monthly_usage(12)
        else:
            data = self.analytics_db.get_daily_usage(30)

        self.time_table.setRowCount(len(data))
        for row, item in enumerate(data):
            self.time_table.setItem(row, 0, QTableWidgetItem(str(item["period"])))
            self.time_table.setItem(row, 1, QTableWidgetItem(str(item["request_count"])))
            self.time_table.setItem(row, 2, QTableWidgetItem(f"{item['input_tokens']:,}"))
            self.time_table.setItem(row, 3, QTableWidgetItem(f"{item['output_tokens']:,}"))
            self.time_table.setItem(row, 4, QTableWidgetItem(f"{item['total_tokens']:,}"))
            speed = f"{item['avg_speed']:.1f}" if item["avg_speed"] else "—"
            self.time_table.setItem(row, 5, QTableWidgetItem(speed))

    def _load_history_table(self):
        records = self.analytics_db.get_recent_requests(150)
        self._all_records = records
        self._populate_history(records)

    def _populate_history(self, records: list[dict]):
        self.history_table.setRowCount(len(records))
        for row, r in enumerate(records):
            self.history_table.setItem(row, 0, QTableWidgetItem(str(r["formatted_time"])))
            self.history_table.setItem(row, 1, QTableWidgetItem(str(r["operation_type"])))
            self.history_table.setItem(row, 2, QTableWidgetItem(str(r["model"])))

            in_tok = str(r["input_tokens"]) if r["input_tokens"] is not None else "—"
            out_tok = str(r["output_tokens"]) if r["output_tokens"] is not None else "—"
            self.history_table.setItem(row, 3, QTableWidgetItem(in_tok))
            self.history_table.setItem(row, 4, QTableWidgetItem(out_tok))

            dur = f"{r['duration_ms']:.0f} ms" if r["duration_ms"] is not None else "—"
            self.history_table.setItem(row, 5, QTableWidgetItem(dur))

            speed = f"{r['tokens_per_second']:.1f} t/s" if r["tokens_per_second"] is not None else "—"
            self.history_table.setItem(row, 6, QTableWidgetItem(speed))

            status_item = QTableWidgetItem(str(r["status"]).upper())
            color = "#3fb950" if r["status"] == "success" else ("#f85149" if r["status"] == "failed" else "#d29922")
            status_item.setForeground(QColor(color))
            self.history_table.setItem(row, 7, status_item)

    def _filter_history(self, query: str):
        query = query.strip().lower()
        if not query or not hasattr(self, "_all_records"):
            self._populate_history(getattr(self, "_all_records", []))
            return
        filtered = [
            r for r in self._all_records
            if query in str(r["model"]).lower()
            or query in str(r["operation_type"]).lower()
            or query in str(r["status"]).lower()
        ]
        self._populate_history(filtered)

    # --- Actions ---

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export AI Analytics CSV",
            str(Path.home() / "openarise_ai_analytics.csv"),
            "CSV Files (*.csv)"
        )
        if not path:
            return
        ok, msg = self.analytics_db.export_to_csv(Path(path))
        if ok:
            QMessageBox.information(self, "Export Complete", msg)
        else:
            QMessageBox.warning(self, "Export Failed", msg)

    def _clear_history(self):
        confirm = QMessageBox.question(
            self,
            "Confirm Clear History",
            "Are you sure you want to delete all recorded AI usage metrics?\n"
            "This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            deleted = self.analytics_db.clear_history()
            QMessageBox.information(self, "History Cleared", f"Cleared {deleted} usage record(s).")
            self.refresh_data()

