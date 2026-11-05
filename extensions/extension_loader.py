"""
Dynamic extension loader for OpenArise IDE.
Loads declarative contributions and executes third-party Python extensions safely.
"""

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

from extensions.models import (
    InstalledExtension,
    ExtensionState,
    ExtensionManifest,
)
from extensions.extension_api import ExtensionContext, ExtensionAPI


@dataclass
class LoadedExtension:
    """Represents an actively running or loaded extension."""
    installed: InstalledExtension
    context: ExtensionContext
    api: ExtensionAPI
    module: Optional[Any] = None
    is_active: bool = False


class ExtensionLoader:
    """
    Manages loading, activation, declarative contribution processing,
    and clean deactivation of extensions.
    """

    def __init__(self):
        self._loaded_extensions: Dict[str, LoadedExtension] = {}

    def is_active(self, extension_id: str) -> bool:
        loaded = self._loaded_extensions.get(extension_id)
        return bool(loaded and loaded.is_active)

    def get_loaded(self, extension_id: str) -> Optional[LoadedExtension]:
        return self._loaded_extensions.get(extension_id)

    def activate_extension(
        self,
        installed: InstalledExtension,
        main_window=None,
        command_registry=None,
        consent_callback: Optional[Callable[[InstalledExtension], bool]] = None,
    ) -> Tuple[bool, str, Optional[LoadedExtension]]:
        """
        Activates an installed extension.
        Enforces security consent checks for Python code extensions before execution.
        """
        manifest = installed.manifest

        if self.is_active(manifest.id):
            return True, f"Extension '{manifest.id}' is already active.", self._loaded_extensions[manifest.id]

        # 1. Security Check: Require explicit consent before executing Python code
        if not manifest.is_declarative and not installed.is_trusted:
            if consent_callback:
                consented = consent_callback(installed)
                if not consented:
                    return False, f"User declined activation of untrusted extension '{manifest.name}'.", None
                installed.is_trusted = True
            else:
                return False, f"Cannot activate untrusted extension '{manifest.name}' without explicit user consent.", None

        # 2. Setup Context & API
        storage_dir = installed.install_dir / "storage"
        storage_dir.mkdir(parents=True, exist_ok=True)
        context = ExtensionContext(
            extension_id=manifest.id,
            extension_dir=installed.install_dir,
            storage_dir=storage_dir,
            manifest=manifest,
        )
        api = ExtensionAPI(context, main_window=main_window, command_registry=command_registry)

        # 3. Process Declarative Contributions (Themes, Snippets)
        contributes = manifest.contributes or {}

        # Themes
        themes = contributes.get("themes", [])
        for theme_def in themes:
            name = theme_def.get("name")
            css = theme_def.get("stylesheet", "")
            css_file = theme_def.get("path")
            if not css and css_file:
                css_path = installed.install_dir / css_file
                if css_path.exists():
                    try:
                        css = css_path.read_text(encoding="utf-8")
                    except Exception:
                        pass
            if name and css:
                api.register_theme(name, css)

        # Snippets
        snippets = contributes.get("snippets", [])
        for snip in snippets:
            prefix = snip.get("prefix")
            body = snip.get("body", "")
            desc = snip.get("description", "")
            if prefix and body:
                api.register_snippet(prefix, body, desc)

        # 4. Load and Execute Python Entry Point (if present)
        mod = None
        if manifest.entry_point:
            entry_file = installed.install_dir / manifest.entry_point
            if not entry_file.exists():
                return False, f"Entry point '{manifest.entry_point}' not found in {installed.install_dir}", None

            module_name = f"openarise_ext_{manifest.id.replace('.', '_').replace('-', '_')}"
            try:
                spec = importlib.util.spec_from_file_location(module_name, str(entry_file))
                if spec is None or spec.loader is None:
                    return False, f"Cannot create module spec for '{entry_file}'", None

                mod = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = mod
                spec.loader.exec_module(mod)

                # Call activate(context, api) if defined
                if hasattr(mod, "activate") and callable(mod.activate):
                    mod.activate(context, api)

            except Exception as exc:
                # Cleanup partially registered disposables on failure
                for disp in reversed(context.subscriptions):
                    try:
                        disp()
                    except Exception:
                        pass
                if module_name in sys.modules:
                    del sys.modules[module_name]
                return False, f"Error activating extension '{manifest.id}': {exc}", None

        loaded = LoadedExtension(
            installed=installed,
            context=context,
            api=api,
            module=mod,
            is_active=True,
        )
        self._loaded_extensions[manifest.id] = loaded
        installed.state = ExtensionState.ACTIVE
        return True, f"Successfully activated {manifest.name}.", loaded

    def deactivate_extension(self, extension_id: str) -> Tuple[bool, str]:
        """
        Deactivates an active extension, calling its deactivate() hook
        and disposing of all registered commands, menus, panels, and themes.
        """
        loaded = self._loaded_extensions.get(extension_id)
        if not loaded or not loaded.is_active:
            return True, f"Extension '{extension_id}' is not active."

        # 1. Call extension's deactivate(context, api) hook if present
        if loaded.module and hasattr(loaded.module, "deactivate") and callable(loaded.module.deactivate):
            try:
                loaded.module.deactivate(loaded.context, loaded.api)
            except Exception:
                pass

        # 2. Execute all registered disposables in reverse order
        for disposable in reversed(loaded.context.subscriptions):
            try:
                disposable()
            except Exception:
                pass
        loaded.context.subscriptions.clear()

        # 3. Clean module from sys.modules
        module_name = f"openarise_ext_{extension_id.replace('.', '_').replace('-', '_')}"
        if module_name in sys.modules:
            del sys.modules[module_name]

        loaded.is_active = False
        loaded.installed.state = ExtensionState.DISABLED
        del self._loaded_extensions[extension_id]
        return True, f"Successfully deactivated {extension_id}."

