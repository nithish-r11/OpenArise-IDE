"""
Central coordinator for the OpenArise IDE Extension System.
Integrates installer, loader, registry, security, and IDE event dispatching.
"""

from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from extensions.models import (
    InstalledExtension,
    ExtensionState,
    RegistryEntry,
    OPENARISE_VERSION,
)
from extensions.extension_installer import ExtensionInstaller, get_default_extensions_dir
from extensions.extension_loader import ExtensionLoader, LoadedExtension
from extensions.extension_registry import ExtensionRegistryClient


class ExtensionManager:
    """
    Main extension manager singleton/coordinator owned by MainWindow.
    Bridges extension events to editor, terminal, AI chat, and command palette.
    """

    def __init__(
        self,
        main_window=None,
        command_registry=None,
        extensions_dir: Optional[Path] = None,
        registry_client: Optional[ExtensionRegistryClient] = None,
        consent_callback: Optional[Callable[[InstalledExtension], bool]] = None,
    ):
        self.main_window = main_window
        self.command_registry = command_registry
        self.installer = ExtensionInstaller(extensions_dir=extensions_dir)
        self.loader = ExtensionLoader()
        self.registry = registry_client or ExtensionRegistryClient()
        self.consent_callback = consent_callback

    @property
    def extensions_dir(self) -> Path:
        return self.installer.extensions_dir

    def startup(self) -> None:
        """Called on application startup. Discovers and auto-activates active extensions."""
        installed_list = self.installer.list_installed()
        for installed in installed_list:
            if installed.state == ExtensionState.ACTIVE:
                # If declarative or already trusted, activate immediately
                if installed.manifest.is_declarative or installed.is_trusted:
                    self.loader.activate_extension(
                        installed,
                        main_window=self.main_window,
                        command_registry=self.command_registry,
                        consent_callback=self.consent_callback,
                    )
                else:
                    # Keep marked as INSTALLED until user consents
                    installed.state = ExtensionState.INSTALLED
                    self.installer.set_extension_state(installed.manifest.id, ExtensionState.INSTALLED)

    def install_from_file(self, package_path: Path) -> Tuple[bool, str, Optional[InstalledExtension]]:
        """Installs a local .oaext package."""
        ok, msg, installed = self.installer.install_package(
            package_path, current_app_version=OPENARISE_VERSION
        )
        if ok and installed and installed.manifest.is_declarative:
            # Declarative extensions (themes, snippets) are safe to auto-activate
            self.loader.activate_extension(
                installed,
                main_window=self.main_window,
                command_registry=self.command_registry,
            )
        return ok, msg, installed

    def install_from_registry(
        self,
        entry: RegistryEntry,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Tuple[bool, str, Optional[InstalledExtension]]:
        """Downloads and installs an extension from the marketplace registry."""
        dl_ok, dl_msg, downloaded_file = self.registry.download_package(
            entry, progress_callback=progress_callback
        )
        if not dl_ok or not downloaded_file:
            return False, f"Failed to download package: {dl_msg}", None

        inst_ok, inst_msg, installed = self.installer.install_package(
            downloaded_file,
            expected_hash=entry.package_hash,
            current_app_version=OPENARISE_VERSION,
        )
        if inst_ok and installed and installed.manifest.is_declarative:
            self.loader.activate_extension(
                installed,
                main_window=self.main_window,
                command_registry=self.command_registry,
            )
        return inst_ok, inst_msg, installed

    def enable_extension(
        self,
        extension_id: str,
        custom_consent: Optional[Callable[[InstalledExtension], bool]] = None,
    ) -> Tuple[bool, str]:
        """Enables and activates an installed extension."""
        installed = self._find_installed(extension_id)
        if not installed:
            return False, f"Extension '{extension_id}' is not installed."

        consent_cb = custom_consent or self.consent_callback
        ok, msg, _ = self.loader.activate_extension(
            installed,
            main_window=self.main_window,
            command_registry=self.command_registry,
            consent_callback=consent_cb,
        )
        if ok:
            self.installer.set_extension_state(extension_id, ExtensionState.ACTIVE)
            if installed.is_trusted:
                self.installer.set_extension_trusted(extension_id, True)
        return ok, msg

    def disable_extension(self, extension_id: str) -> Tuple[bool, str]:
        """Disables and deactivates an active extension."""
        ok, msg = self.loader.deactivate_extension(extension_id)
        if ok:
            self.installer.set_extension_state(extension_id, ExtensionState.DISABLED)
        return ok, msg

    def uninstall_extension(self, extension_id: str) -> Tuple[bool, str]:
        """Deactivates and removes an extension from disk."""
        if self.loader.is_active(extension_id):
            self.loader.deactivate_extension(extension_id)
        return self.installer.uninstall_extension(extension_id)

    def update_extension(
        self,
        extension_id: str,
        newer_entry: RegistryEntry,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Tuple[bool, str]:
        """Updates an extension to a newer registry version."""
        was_active = self.loader.is_active(extension_id)
        if was_active:
            self.loader.deactivate_extension(extension_id)

        inst_ok, inst_msg, installed = self.install_from_registry(newer_entry, progress_callback)
        if not inst_ok or not installed:
            return False, f"Update failed: {inst_msg}"

        if was_active:
            self.enable_extension(extension_id)

        return True, f"Successfully updated '{extension_id}' to v{newer_entry.version}."

    def list_installed(self) -> List[InstalledExtension]:
        """Returns all installed extensions, updating state to reflect runtime active state."""
        installed_list = self.installer.list_installed()
        for ext in installed_list:
            if self.loader.is_active(ext.manifest.id):
                ext.state = ExtensionState.ACTIVE
        return installed_list

    def is_active(self, extension_id: str) -> bool:
        return self.loader.is_active(extension_id)

    def _find_installed(self, extension_id: str) -> Optional[InstalledExtension]:
        for ext in self.installer.list_installed():
            if ext.manifest.id == extension_id:
                return ext
        return None

    # Event dispatchers called by MainWindow
    def dispatch_file_open(self, file_path: str) -> None:
        for loaded in list(self.loader._loaded_extensions.values()):
            if loaded.is_active and loaded.api:
                loaded.api.dispatch_file_open(file_path)

    def dispatch_file_save(self, file_path: str) -> None:
        for loaded in list(self.loader._loaded_extensions.values()):
            if loaded.is_active and loaded.api:
                loaded.api.dispatch_file_save(file_path)

    def dispatch_chat_prompt(self, prompt: str) -> str:
        current_prompt = prompt
        for loaded in list(self.loader._loaded_extensions.values()):
            if loaded.is_active and loaded.api:
                current_prompt = loaded.api.dispatch_chat_prompt(current_prompt)
        return current_prompt

