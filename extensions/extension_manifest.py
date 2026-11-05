"""
Manifest schema validation and version compatibility checking.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from extensions.models import ExtensionManifest, OPENARISE_VERSION


ID_REGEX = re.compile(r"^[a-zA-Z0-9_]+(\.[a-zA-Z0-9_-]+)+$")
SEMVER_REGEX = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?$")


def parse_semver(version_str: str) -> Tuple[int, int, int]:
    """Parses a version string into (major, minor, patch) integers."""
    match = SEMVER_REGEX.match(version_str.strip())
    if not match:
        raise ValueError(f"Invalid semver version string: '{version_str}'")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def is_version_compatible(app_version: str, min_version: str) -> bool:
    """Returns True if app_version >= min_version."""
    try:
        app_parts = parse_semver(app_version)
        min_parts = parse_semver(min_version)
        return app_parts >= min_parts
    except ValueError:
        return False


class ManifestValidator:
    """Validates manifest dictionaries and JSON files against OpenArise rules."""

    REQUIRED_FIELDS = ["id", "name", "version", "description", "author", "category"]

    @classmethod
    def validate_dict(cls, data: Dict[str, Any], current_app_version: str = OPENARISE_VERSION) -> Tuple[bool, List[str], Optional[ExtensionManifest]]:
        errors: List[str] = []

        if not isinstance(data, dict):
            return False, ["Manifest must be a JSON object."], None

        # Check required fields
        for field in cls.REQUIRED_FIELDS:
            val = data.get(field)
            if not val or not str(val).strip():
                errors.append(f"Missing required field: '{field}'")

        # Validate ID format
        ext_id = str(data.get("id", "")).strip()
        if ext_id and not ID_REGEX.match(ext_id):
            errors.append(f"Invalid extension ID '{ext_id}'. Must be in 'publisher.name' dot-separated format (e.g. 'openarise.python-essentials').")

        # Validate semver
        version = str(data.get("version", "")).strip()
        if version:
            try:
                parse_semver(version)
            except ValueError:
                errors.append(f"Invalid extension version '{version}'. Must follow semantic versioning (e.g. '1.0.0').")

        # Validate minimum_openarise_version
        min_ver = str(data.get("minimum_openarise_version", "1.0.0")).strip()
        try:
            parse_semver(min_ver)
            if not is_version_compatible(current_app_version, min_ver):
                errors.append(
                    f"Extension requires OpenArise IDE version >= {min_ver}, but current version is {current_app_version}."
                )
        except ValueError:
            errors.append(f"Invalid minimum_openarise_version format: '{min_ver}'.")

        # Permissions check
        permissions = data.get("permissions", [])
        if not isinstance(permissions, list):
            errors.append("'permissions' must be a list of strings.")

        # Entry point check
        entry_point = data.get("entry_point")
        if entry_point is not None:
            if not isinstance(entry_point, str) or not entry_point.strip():
                errors.append("'entry_point' must be a valid file path or null.")
            elif not entry_point.endswith(".py"):
                errors.append(f"'entry_point' must be a Python file (.py), received: '{entry_point}'.")

        if errors:
            return False, errors, None

        manifest = ExtensionManifest.from_dict(data)
        return True, [], manifest

    @classmethod
    def validate_file(cls, path: Path, current_app_version: str = OPENARISE_VERSION) -> Tuple[bool, List[str], Optional[ExtensionManifest]]:
        p = Path(path)
        if not p.exists() or not p.is_file():
            return False, [f"Manifest file not found: {p}"], None
        try:
            content = p.read_text(encoding="utf-8")
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            return False, [f"Malformed JSON in manifest: {exc}"], None
        except Exception as exc:
            return False, [f"Error reading manifest: {exc}"], None

        return cls.validate_dict(data, current_app_version=current_app_version)

