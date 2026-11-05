"""
OpenArise IDE Extension Marketplace Panel.
Provides Browse, Installed, and Updates views with search, details,
permission inspection, and local package installation.
"""

from pathlib import Path
from typing import Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QComboBox,
    QPushButton,
    QTabWidget,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QTextBrowser,
    QSplitter,
    QProgressBar,
    QMessageBox,
    QFileDialog,
    QDialog,
    QDialogButtonBox,
    QScrollArea,
    QFrame,
)

from extensions.models import (
    InstalledExtension,
    RegistryEntry,
    ExtensionState,
    PERMISSION_DESCRIPTIONS,
)
from extensions.extension_manager import ExtensionManager


class SecurityConsentDialog(QDialog):
    """
    Modal dialog requiring explicit user consent before activating third-party Python code.
    """

    def __init__(self, ext_name: str, ext_id: str, author: str, permissions: List[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Security Warning — Enable Extension")
        self.setMinimumWidth(480)
        self.setStyleSheet("background-color: #1a1d26; color: #e6e8ef;")

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(18, 18, 18, 18)

        # Header warning
        warn_title = QLabel("⚠️ Third-Party Executable Python Code")
        warn_title.setStyleSheet("font-size: 12pt; font-weight: bold; color: #f78c6c;")
        layout.addWidget(warn_title)

        msg = QLabel(
            f"The extension <b>{ext_name}</b> (<code>{ext_id}</code>) by <i>{author}</i> "
            f"contains executable Python code."
        )
        msg.setWordWrap(True)
        layout.addWidget(msg)

        disclaimer = QLabel(
            "<b>Important:</b> Ordinary Python plugins run directly inside the OpenArise process with your full user permissions "
            "and are not OS-sandboxed. Only activate extensions from trusted sources."
        )
        disclaimer.setStyleSheet("background: #252a36; border: 1px solid #3d4963; border-radius: 4px; padding: 8px; color: #d7dae0;")
        disclaimer.setWordWrap(True)
        layout.addWidget(disclaimer)

        # Permissions
        if permissions:
            perm_header = QLabel("Requested Capabilities & Permissions:")
            perm_header.setStyleSheet("font-weight: 600; color: #8ab4f8; margin-top: 6px;")
            layout.addWidget(perm_header)

            perm_box = QFrame()
            perm_box.setStyleSheet("background: #171920; border: 1px solid #2b3345; border-radius: 4px; padding: 6px;")
            perm_layout = QVBoxLayout(perm_box)
            perm_layout.setSpacing(4)
            for p in permissions:
                desc = PERMISSION_DESCRIPTIONS.get(p, "Custom capability")
                lbl = QLabel(f"• <b>{p}</b>: {desc}")
                lbl.setWordWrap(True)
                lbl.setStyleSheet("font-size: 9pt; color: #a4b3cf;")
                perm_layout.addWidget(lbl)
            layout.addWidget(perm_box)

        # Dialog Buttons
        btn_box = QDialogButtonBox()
        self.allow_btn = btn_box.addButton("Trust & Enable", QDialogButtonBox.ButtonRole.AcceptRole)
        self.allow_btn.setStyleSheet("background: #2ea043; color: white; padding: 6px 14px; font-weight: bold; border-radius: 4px;")
        self.cancel_btn = btn_box.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
        self.cancel_btn.setStyleSheet("background: #373e4d; color: #e6e8ef; padding: 6px 14px; border-radius: 4px;")

        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)


class ExtensionCardWidget(QWidget):
    """
    Renders an extension item inside list views (Browse, Installed, Updates).
    """

    def __init__(self, name: str, version: str, author: str, category: str, description: str, status_text: str = "", status_color: str = "#8ab4f8", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        # Top row: Name, Version, Status Pill
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        name_lbl = QLabel(name)
        name_lbl.setStyleSheet("font-weight: 600; font-size: 10pt; color: #ffffff;")
        top_row.addWidget(name_lbl)

        ver_lbl = QLabel(f"v{version}")
        ver_lbl.setStyleSheet("color: #79869c; font-size: 8.5pt;")
        top_row.addWidget(ver_lbl)

        top_row.addStretch(1)

        if status_text:
            pill = QLabel(status_text)
            pill.setStyleSheet(
                f"background: #1f2636; color: {status_color}; border: 1px solid #33405b; "
                f"border-radius: 4px; padding: 1px 6px; font-size: 8pt; font-weight: 500;"
            )
            top_row.addWidget(pill)

        layout.addLayout(top_row)

        # Middle row: Description
        desc_lbl = QLabel(description or "No description provided.")
        desc_lbl.setStyleSheet("color: #9aa4b5; font-size: 9pt;")
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl)

        # Bottom row: Author and Category
        meta_row = QHBoxLayout()
        author_lbl = QLabel(f"by {author}")
        author_lbl.setStyleSheet("color: #687386; font-size: 8pt;")
        meta_row.addWidget(author_lbl)

        sep = QLabel("•")
        sep.setStyleSheet("color: #4a5468; font-size: 8pt;")
        meta_row.addWidget(sep)

        cat_lbl = QLabel(category)
        cat_lbl.setStyleSheet("color: #687386; font-size: 8pt;")
        meta_row.addWidget(cat_lbl)

        meta_row.addStretch(1)
        layout.addLayout(meta_row)


class ExtensionsPanel(QWidget):
    """
    Main Extensions view containing Browse, Installed, and Updates tabs
    with search, category filters, and detailed view.
    """

    extension_state_changed = pyqtSignal()

    def __init__(self, extension_manager: ExtensionManager, parent=None):
        super().__init__(parent)
        self.manager = extension_manager
        self.selected_item = None
        self._build_ui()
        self.refresh_all()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(6, 6, 6, 6)
        root_layout.setSpacing(8)

        # Header bar: Title, Install button, Refresh button
        header_row = QHBoxLayout()
        title_lbl = QLabel("Extensions")
        title_lbl.setStyleSheet("font-size: 11pt; font-weight: bold; color: #e6e8ef;")
        header_row.addWidget(title_lbl)
        header_row.addStretch(1)

        self.install_file_btn = QPushButton("Install from .oaext…")
        self.install_file_btn.setToolTip("Install extension from local .oaext file")
        self.install_file_btn.setStyleSheet("background: #2a344a; color: #8ab4f8; border: 1px solid #3d4f73; border-radius: 4px; padding: 4px 8px; font-size: 8.5pt;")
        self.install_file_btn.clicked.connect(self._on_install_from_file_clicked)
        header_row.addWidget(self.install_file_btn)

        self.refresh_btn = QPushButton("🔄")
        self.refresh_btn.setToolTip("Refresh marketplace catalog")
        self.refresh_btn.setFixedWidth(28)
        self.refresh_btn.setStyleSheet("background: #2a344a; color: #e6e8ef; border: 1px solid #3d4f73; border-radius: 4px; padding: 4px;")
        self.refresh_btn.clicked.connect(self.refresh_all)
        header_row.addWidget(self.refresh_btn)

        root_layout.addLayout(header_row)

        # Search Bar and Category Filter
        filter_row = QHBoxLayout()
        filter_row.setSpacing(6)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search extensions in marketplace…")
        self.search_input.setStyleSheet("background: #1b1e26; border: 1px solid #333d52; border-radius: 4px; padding: 5px; color: #fff;")
        self.search_input.textChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self.search_input, 1)

        self.category_combo = QComboBox()
        self.category_combo.addItems(["All Categories", "Programming", "Themes", "Formatters", "AI", "Tools"])
        self.category_combo.setStyleSheet("background: #1b1e26; border: 1px solid #333d52; border-radius: 4px; padding: 4px; color: #fff;")
        self.category_combo.currentTextChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self.category_combo)

        root_layout.addLayout(filter_row)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("QProgressBar { background: #1b1e26; border: 0; } QProgressBar::chunk { background: #65d98b; }")
        self.progress_bar.hide()
        root_layout.addWidget(self.progress_bar)

        # Splitter: Left (Tabs) & Right (Details)
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)

        # Tabs: Browse, Installed, Updates
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid #2b3345; background: #141720; }"
            "QTabBar::tab { background: #1b1f2b; color: #9aa4b5; padding: 6px 14px; border: 1px solid #2b3345; }"
            "QTabBar::tab:selected { background: #262c3d; color: #ffffff; font-weight: bold; }"
        )

        # Browse list
        self.browse_list = QListWidget()
        self.browse_list.setStyleSheet("background: #141720; border: 0;")
        self.browse_list.itemClicked.connect(lambda item: self._display_details(item.data(Qt.ItemDataRole.UserRole)))
        self.tabs.addTab(self.browse_list, "Browse")

        # Installed list
        self.installed_list = QListWidget()
        self.installed_list.setStyleSheet("background: #141720; border: 0;")
        self.installed_list.itemClicked.connect(lambda item: self._display_details(item.data(Qt.ItemDataRole.UserRole)))
        self.tabs.addTab(self.installed_list, "Installed")

        # Updates list
        self.updates_list = QListWidget()
        self.updates_list.setStyleSheet("background: #141720; border: 0;")
        self.updates_list.itemClicked.connect(lambda item: self._display_details(item.data(Qt.ItemDataRole.UserRole)))
        self.tabs.addTab(self.updates_list, "Updates")

        splitter.addWidget(self.tabs)

        # Details Pane
        self.details_widget = QWidget()
        details_layout = QVBoxLayout(self.details_widget)
        details_layout.setContentsMargins(8, 8, 8, 8)
        details_layout.setSpacing(6)

        self.details_title = QLabel("Select an extension to view details")
        self.details_title.setStyleSheet("font-size: 11pt; font-weight: bold; color: #e6e8ef;")
        details_layout.addWidget(self.details_title)

        self.details_meta = QLabel("")
        self.details_meta.setStyleSheet("font-size: 8.5pt; color: #79869c;")
        details_layout.addWidget(self.details_meta)

        self.details_trust = QLabel("")
        self.details_trust.setStyleSheet("font-size: 8.5pt; padding: 3px 6px; border-radius: 4px;")
        self.details_trust.setWordWrap(True)
        details_layout.addWidget(self.details_trust)

        # Details Actions bar (Install / Enable / Disable / Uninstall / Update)
        self.actions_row = QHBoxLayout()
        self.actions_row.setSpacing(6)

        self.action_primary_btn = QPushButton("Install")
        self.action_primary_btn.setStyleSheet("background: #2ea043; color: white; font-weight: bold; border-radius: 4px; padding: 4px 12px;")
        self.action_primary_btn.clicked.connect(self._on_primary_action_clicked)
        self.action_primary_btn.hide()
        self.actions_row.addWidget(self.action_primary_btn)

        self.action_secondary_btn = QPushButton("Uninstall")
        self.action_secondary_btn.setStyleSheet("background: #a42c2c; color: white; border-radius: 4px; padding: 4px 12px;")
        self.action_secondary_btn.clicked.connect(self._on_secondary_action_clicked)
        self.action_secondary_btn.hide()
        self.actions_row.addWidget(self.action_secondary_btn)

        self.actions_row.addStretch(1)
        details_layout.addLayout(self.actions_row)

        # Text browser for README / permissions
        self.details_browser = QTextBrowser()
        self.details_browser.setStyleSheet("background: #171920; border: 1px solid #2b3345; color: #d7dae0; font-size: 9pt;")
        details_layout.addWidget(self.details_browser, 1)

        splitter.addWidget(self.details_widget)
        splitter.setSizes([380, 240])

        root_layout.addWidget(splitter, 1)

    def refresh_all(self):
        """Fetches catalog and reloads installed list."""
        self.manager.registry.fetch_catalog(force_refresh=True)
        self._populate_views()

    def _on_filter_changed(self):
        self._populate_views()

    def _matches_filter(self, name: str, ext_id: str, desc: str, cat: str) -> bool:
        query = self.search_input.text().strip().lower()
        cat_filter = self.category_combo.currentText()

        if cat_filter != "All Categories" and cat.lower() != cat_filter.lower():
            return False

        if query:
            return (
                query in name.lower()
                or query in ext_id.lower()
                or query in desc.lower()
                or query in cat.lower()
            )
        return True

    def _populate_views(self):
        # 1. Installed
        self.installed_list.clear()
        installed_exts = self.manager.list_installed()
        for ext in installed_exts:
            m = ext.manifest
            if self._matches_filter(m.name, m.id, m.description, m.category):
                is_active = self.manager.is_active(m.id)
                status_text = "Active" if is_active else "Disabled"
                status_color = "#65d98b" if is_active else "#9aa4b5"

                item = QListWidgetItem(self.installed_list)
                card = ExtensionCardWidget(m.name, m.version, m.author, m.category, m.description, status_text, status_color)
                item.setSizeHint(card.sizeHint())
                item.setData(Qt.ItemDataRole.UserRole, ext)
                self.installed_list.addItem(item)
                self.installed_list.setItemWidget(item, card)

        self.tabs.setTabText(1, f"Installed ({len(installed_exts)})")

        # 2. Browse (Catalog)
        self.browse_list.clear()
        catalog_entries = list(self.manager.registry._cached_catalog.values())
        installed_ids = {e.manifest.id: e for e in installed_exts}

        for entry in catalog_entries:
            if self._matches_filter(entry.name, entry.id, entry.description, entry.category):
                status_text = ""
                status_color = "#8ab4f8"
                if entry.id in installed_ids:
                    status_text = "Installed"
                    status_color = "#65d98b"

                item = QListWidgetItem(self.browse_list)
                card = ExtensionCardWidget(entry.name, entry.version, entry.author, entry.category, entry.description, status_text, status_color)
                item.setSizeHint(card.sizeHint())
                item.setData(Qt.ItemDataRole.UserRole, entry)
                self.browse_list.addItem(item)
                self.browse_list.setItemWidget(item, card)

        self.tabs.setTabText(0, f"Browse ({len(catalog_entries)})")

        # 3. Updates
        self.updates_list.clear()
        updates = self.manager.registry.check_updates(installed_exts)
        for installed, newer in updates:
            item = QListWidgetItem(self.updates_list)
            card = ExtensionCardWidget(
                installed.manifest.name,
                f"{installed.manifest.version} ➔ {newer.version}",
                installed.manifest.author,
                installed.manifest.category,
                newer.description,
                "Update Available",
                "#f78c6c",
            )
            item.setSizeHint(card.sizeHint())
            item.setData(Qt.ItemDataRole.UserRole, (installed, newer))
            self.updates_list.addItem(item)
            self.updates_list.setItemWidget(item, card)

        self.tabs.setTabText(2, f"Updates ({len(updates)})")

    def _display_details(self, data):
        self.selected_item = data
        if not data:
            return

        if isinstance(data, tuple) and len(data) == 2:
            # (InstalledExtension, newer_RegistryEntry)
            installed, newer = data
            manifest = installed.manifest
            version_str = f"{manifest.version} (Update available: v{newer.version})"
            is_installed = True
            is_active = self.manager.is_active(manifest.id)
            readme = newer.readme or installed.readme_content
            permissions = newer.permissions or manifest.permissions
            is_declarative = newer.is_declarative
        elif isinstance(data, InstalledExtension):
            manifest = data.manifest
            version_str = manifest.version
            is_installed = True
            is_active = self.manager.is_active(manifest.id)
            readme = data.readme_content
            permissions = manifest.permissions
            is_declarative = manifest.is_declarative
        elif isinstance(data, RegistryEntry):
            manifest = data
            version_str = manifest.version
            is_installed = any(e.manifest.id == data.id for e in self.manager.list_installed())
            is_active = self.manager.is_active(data.id) if is_installed else False
            readme = data.readme
            permissions = data.permissions
            is_declarative = data.is_declarative
        else:
            return

        self.details_title.setText(manifest.name)
        self.details_meta.setText(f"ID: {manifest.id}  •  Version: {version_str}  •  Author: {manifest.author}  •  Category: {manifest.category}")

        if is_declarative:
            self.details_trust.setText("🛡️ Declarative Extension: Contains themes/snippets only. Safe to run without Python code execution.")
            self.details_trust.setStyleSheet("background: #1b2d24; color: #65d98b; border: 1px solid #2e5941;")
        else:
            self.details_trust.setText("⚠️ Executable Python Extension: Runs with standard user privileges in IDE process.")
            self.details_trust.setStyleSheet("background: #33241b; color: #f78c6c; border: 1px solid #5a3e2e;")

        # Update action buttons
        self.action_primary_btn.show()
        if is_installed:
            if isinstance(data, tuple):
                self.action_primary_btn.setText("Update")
                self.action_primary_btn.setStyleSheet("background: #0969da; color: white; font-weight: bold; border-radius: 4px; padding: 4px 12px;")
            elif is_active:
                self.action_primary_btn.setText("Disable")
                self.action_primary_btn.setStyleSheet("background: #6e7681; color: white; font-weight: bold; border-radius: 4px; padding: 4px 12px;")
            else:
                self.action_primary_btn.setText("Enable")
                self.action_primary_btn.setStyleSheet("background: #2ea043; color: white; font-weight: bold; border-radius: 4px; padding: 4px 12px;")

            self.action_secondary_btn.show()
            self.action_secondary_btn.setText("Uninstall")
        else:
            self.action_primary_btn.setText("Install")
            self.action_primary_btn.setStyleSheet("background: #2ea043; color: white; font-weight: bold; border-radius: 4px; padding: 4px 12px;")
            self.action_secondary_btn.hide()

        # Build README / Details HTML
        html = f"<h3>Description</h3><p>{manifest.description}</p>"

        if permissions:
            html += "<h4>Requested Permissions:</h4><ul>"
            for p in permissions:
                desc = PERMISSION_DESCRIPTIONS.get(p, "Custom capability")
                html += f"<li><b>{p}</b>: {desc}</li>"
            html += "</ul>"

        if readme:
            html += f"<hr><h3>README</h3><pre style='font-family: Segoe UI, sans-serif;'>{readme}</pre>"

        self.details_browser.setHtml(html)

    def _on_primary_action_clicked(self):
        text = self.action_primary_btn.text()
        if not self.selected_item:
            return

        if text == "Install":
            entry = self.selected_item
            if isinstance(entry, RegistryEntry):
                self._run_install_registry(entry)
        elif text == "Enable":
            ext = self.selected_item
            ext_id = ext.manifest.id if hasattr(ext, "manifest") else ext.id
            self._run_enable(ext_id)
        elif text == "Disable":
            ext = self.selected_item
            ext_id = ext.manifest.id if hasattr(ext, "manifest") else ext.id
            self._run_disable(ext_id)
        elif text == "Update":
            installed, newer = self.selected_item
            self._run_update(installed.manifest.id, newer)

    def _on_secondary_action_clicked(self):
        if not self.selected_item:
            return
        ext = self.selected_item
        if isinstance(ext, tuple):
            ext = ext[0]
        ext_id = ext.manifest.id if hasattr(ext, "manifest") else ext.id

        confirm = QMessageBox.question(
            self,
            "Uninstall Extension",
            f"Are you sure you want to uninstall '{ext_id}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            ok, msg = self.manager.uninstall_extension(ext_id)
            if ok:
                self.refresh_all()
                self.extension_state_changed.emit()
            else:
                QMessageBox.critical(self, "Uninstall Error", msg)

    def _run_enable(self, extension_id: str):
        # Explicit security consent callback for Python extensions
        def consent_prompt(installed: InstalledExtension) -> bool:
            dlg = SecurityConsentDialog(
                ext_name=installed.manifest.name,
                ext_id=installed.manifest.id,
                author=installed.manifest.author,
                permissions=installed.manifest.permissions,
                parent=self,
            )
            return dlg.exec() == QDialog.DialogCode.Accepted

        ok, msg = self.manager.enable_extension(extension_id, custom_consent=consent_prompt)
        if ok:
            self.refresh_all()
            self._display_details(self.selected_item)
            self.extension_state_changed.emit()
        else:
            QMessageBox.warning(self, "Enable Failed", msg)

    def _run_disable(self, extension_id: str):
        ok, msg = self.manager.disable_extension(extension_id)
        if ok:
            self.refresh_all()
            self._display_details(self.selected_item)
            self.extension_state_changed.emit()
        else:
            QMessageBox.warning(self, "Disable Failed", msg)

    def _run_install_registry(self, entry: RegistryEntry):
        self.progress_bar.show()
        self.progress_bar.setRange(0, 0)
        try:
            ok, msg, installed = self.manager.install_from_registry(entry)
            self.progress_bar.hide()
            if ok:
                self.refresh_all()
                self._display_details(installed)
                self.extension_state_changed.emit()
            else:
                QMessageBox.critical(self, "Installation Failed", msg)
        finally:
            self.progress_bar.hide()

    def _run_update(self, extension_id: str, newer_entry: RegistryEntry):
        self.progress_bar.show()
        self.progress_bar.setRange(0, 0)
        try:
            ok, msg = self.manager.update_extension(extension_id, newer_entry)
            self.progress_bar.hide()
            if ok:
                self.refresh_all()
                self.extension_state_changed.emit()
            else:
                QMessageBox.critical(self, "Update Failed", msg)
        finally:
            self.progress_bar.hide()

    def _on_install_from_file_clicked(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Install OpenArise Extension",
            "",
            "OpenArise Extension (*.oaext);;ZIP Archive (*.zip);;All Files (*)",
        )
        if not file_path:
            return

        ok, msg, installed = self.manager.install_from_file(Path(file_path))
        if ok and installed:
            QMessageBox.information(self, "Extension Installed", msg)
            self.refresh_all()
            self._display_details(installed)
            self.extension_state_changed.emit()
        else:
            QMessageBox.critical(self, "Installation Failed", msg)

