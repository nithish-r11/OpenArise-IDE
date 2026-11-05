"""
Data models and enumerations for the OpenArise IDE Extension System.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

OPENARISE_VERSION = "1.0.0"


class ExtensionState(str, Enum):
    AVAILABLE = "available"
    INSTALLED = "installed"
    ACTIVE = "active"
    DISABLED = "disabled"
    ERROR = "error"


class ExtensionPermission(str, Enum):
    COMMANDS = "commands"
    EDITOR = "editor"
    TERMINAL = "terminal"
    THEMES = "themes"
    CHAT = "chat"
    FILESYSTEM = "filesystem"
    NETWORK = "network"


PERMISSION_DESCRIPTIONS = {
    ExtensionPermission.COMMANDS.value: "Register custom commands in the Command Palette and menus.",
    ExtensionPermission.EDITOR.value: "Inspect, insert, format, or modify text in open editor buffers.",
    ExtensionPermission.TERMINAL.value: "Send commands to or inspect output from the integrated terminal.",
    ExtensionPermission.THEMES.value: "Register and apply custom UI color themes and styling.",
    ExtensionPermission.CHAT.value: "Interact with the AI chat panel, inject prompts, or listen to queries.",
    ExtensionPermission.FILESYSTEM.value: "Read and write project files directly via Python APIs.",
    ExtensionPermission.NETWORK.value: "Make external outbound network or HTTP requests.",
}


@dataclass
class ExtensionManifest:
    id: str
    name: str
    version: str
    description: str
    author: str
    category: str
    minimum_openarise_version: str = "1.0.0"
    entry_point: Optional[str] = None
    permissions: List[str] = field(default_factory=list)
    package_hash: str = ""
    contributes: Dict[str, Any] = field(default_factory=dict)
    homepage: str = ""
    repository: str = ""

    @property
    def is_declarative(self) -> bool:
        """True if the extension does NOT contain executable Python code."""
        return not bool(self.entry_point and self.entry_point.strip())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "category": self.category,
            "minimum_openarise_version": self.minimum_openarise_version,
            "entry_point": self.entry_point,
            "permissions": self.permissions,
            "package_hash": self.package_hash,
            "contributes": self.contributes,
            "homepage": self.homepage,
            "repository": self.repository,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExtensionManifest":
        return cls(
            id=str(data.get("id", "")).strip(),
            name=str(data.get("name", "")).strip(),
            version=str(data.get("version", "1.0.0")).strip(),
            description=str(data.get("description", "")).strip(),
            author=str(data.get("author", "Unknown")).strip(),
            category=str(data.get("category", "General")).strip(),
            minimum_openarise_version=str(data.get("minimum_openarise_version", "1.0.0")).strip(),
            entry_point=data.get("entry_point") or None,
            permissions=list(data.get("permissions", [])),
            package_hash=str(data.get("package_hash", "")).strip(),
            contributes=dict(data.get("contributes", {})),
            homepage=str(data.get("homepage", "")).strip(),
            repository=str(data.get("repository", "")).strip(),
        )


@dataclass
class RegistryEntry:
    """Catalog metadata for an extension in the online or local marketplace."""
    id: str
    name: str
    version: str
    description: str
    author: str
    category: str
    download_url: str
    package_hash: str
    minimum_openarise_version: str = "1.0.0"
    entry_point: Optional[str] = None
    permissions: List[str] = field(default_factory=list)
    contributes: Dict[str, Any] = field(default_factory=dict)
    icon: str = ""
    readme: str = ""

    @property
    def is_declarative(self) -> bool:
        return not bool(self.entry_point and self.entry_point.strip())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "category": self.category,
            "download_url": self.download_url,
            "package_hash": self.package_hash,
            "minimum_openarise_version": self.minimum_openarise_version,
            "entry_point": self.entry_point,
            "permissions": self.permissions,
            "contributes": self.contributes,
            "icon": self.icon,
            "readme": self.readme,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RegistryEntry":
        return cls(
            id=str(data.get("id", "")).strip(),
            name=str(data.get("name", "")).strip(),
            version=str(data.get("version", "1.0.0")).strip(),
            description=str(data.get("description", "")).strip(),
            author=str(data.get("author", "Unknown")).strip(),
            category=str(data.get("category", "General")).strip(),
            download_url=str(data.get("download_url", "")).strip(),
            package_hash=str(data.get("package_hash", "")).strip(),
            minimum_openarise_version=str(data.get("minimum_openarise_version", "1.0.0")).strip(),
            entry_point=data.get("entry_point") or None,
            permissions=list(data.get("permissions", [])),
            contributes=dict(data.get("contributes", {})),
            icon=str(data.get("icon", "")).strip(),
            readme=str(data.get("readme", "")).strip(),
        )


@dataclass
class InstalledExtension:
    """Represents an unpacked and installed extension on disk."""
    manifest: ExtensionManifest
    install_dir: Path
    state: ExtensionState = ExtensionState.INSTALLED
    is_trusted: bool = False
    error_message: Optional[str] = None
    readme_content: str = ""
    package_file: Optional[Path] = None

