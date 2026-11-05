"""
Package installer and uninstaller for OpenArise IDE extensions (.oaext).
Manages extraction, directory layouts, and state persistence.
"""

import json
import os
import shutil
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from extensions.models import (
    ExtensionManifest,
    ExtensionState,
    InstalledExtension,
    OPENARISE_VERSION,
)
from extensions.extension_manifest import ManifestValidator
from extensions.extension_security import ExtensionSecurity, SecurityException


def get_default_extensions_dir() -> Path:
    """Returns %LOCALAPPDATA%/OpenAriseIDE/extensions/ on Windows, or ~/.openarise/extensions/ fallback."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        base = Path(local_app_data) / "OpenAriseIDE" / "extensions"
    else:
        base = Path.home() / ".openarise" / "extensions"
    return base


class ExtensionInstaller:
    """
    Handles local .oaext file validation, installation, uninstallation,
    and state tracking in extensions_state.json.
    """

    def __init__(self, extensions_dir: Optional[Path] = None):
        if extensions_dir is None:
            self.extensions_dir = get_default_extensions_dir()
        else:
            self.extensions_dir = Path(extensions_dir).resolve()

        self.extensions_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.extensions_dir / "extensions_state.json"
        self._state_data: Dict[str, Dict] = self._load_state()

    def _load_state(self) -> Dict[str, Dict]:
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
        return {}

    def _save_state(self) -> None:
        try:
            temp_file = self.state_file.parent / f"{self.state_file.name}.tmp"
            temp_file.write_text(json.dumps(self._state_data, indent=2), encoding="utf-8")
            temp_file.replace(self.state_file)
        except Exception:
            pass

    def install_package(
        self,
        package_path: Path,
        expected_hash: Optional[str] = None,
        current_app_version: str = OPENARISE_VERSION,
    ) -> Tuple[bool, str, Optional[InstalledExtension]]:
        """
        Validates and installs a .oaext archive into %LOCALAPPDATA%/OpenAriseIDE/extensions/<id>/<version>/.
        Never executes Python code during installation.
        """
        package = Path(package_path).resolve()
        if not package.exists() or not package.is_file():
            return False, f"Package file not found: {package}", None

        # 1. SHA-256 verification
        if expected_hash:
            matches, actual_hash = ExtensionSecurity.verify_package_hash(package, expected_hash)
            if not matches:
                return False, f"SHA-256 hash mismatch. Expected '{expected_hash}', calculated '{actual_hash}'.", None
        else:
            actual_hash = ExtensionSecurity.calculate_sha256(package)

        # 2. Inspect manifest from ZIP before extracting
        try:
            with zipfile.ZipFile(package, "r") as zf:
                if "manifest.json" not in zf.namelist():
                    return False, "Package is missing required 'manifest.json'.", None

                manifest_raw = zf.read("manifest.json").decode("utf-8", errors="replace")
                try:
                    manifest_data = json.loads(manifest_raw)
                except json.JSONDecodeError as exc:
                    return False, f"Invalid JSON in manifest.json: {exc}", None

                valid, errors, manifest = ManifestValidator.validate_dict(
                    manifest_data, current_app_version=current_app_version
                )
                if not valid or not manifest:
                    return False, f"Manifest validation failed: {'; '.join(errors)}", None

        except zipfile.BadZipFile:
            return False, f"Corrupted or invalid ZIP/oaext package: {package.name}", None
        except Exception as exc:
            return False, f"Cannot read package: {exc}", None

        # Update package_hash in manifest if missing
        if not manifest.package_hash:
            manifest.package_hash = actual_hash

        # 3. Target directory layout: <extensions_dir>/<id>/<version>/
        target_dir = self.extensions_dir / manifest.id / manifest.version
        if target_dir.exists():
            try:
                shutil.rmtree(target_dir, ignore_errors=True)
            except Exception:
                pass
        target_dir.mkdir(parents=True, exist_ok=True)

        # 4. Safe ZIP extraction with path traversal protection
        try:
            ExtensionSecurity.safe_extract_zip(package, target_dir)
        except SecurityException as sec_err:
            # Clean up aborted extraction
            shutil.rmtree(target_dir, ignore_errors=True)
            return False, f"Security violation during package extraction: {sec_err}", None
        except Exception as exc:
            shutil.rmtree(target_dir, ignore_errors=True)
            return False, f"Extraction failed: {exc}", None

        # 5. Read README if available
        readme_content = ""
        for name in ("README.md", "readme.md", "README.txt"):
            r_path = target_dir / name
            if r_path.exists():
                try:
                    readme_content = r_path.read_text(encoding="utf-8", errors="replace")
                    break
                except Exception:
                    pass

        # 6. Record state (default to INSTALLED; declarative extensions can default to ACTIVE)
        default_state = ExtensionState.ACTIVE if manifest.is_declarative else ExtensionState.INSTALLED
        prev_trusted = self._state_data.get(manifest.id, {}).get("is_trusted", False)

        self._state_data[manifest.id] = {
            "version": manifest.version,
            "install_dir": str(target_dir),
            "state": default_state.value,
            "is_trusted": prev_trusted or manifest.is_declarative,
            "installed_at": os.path.getmtime(package) if package.exists() else 0,
            "package_file": str(package),
            "package_hash": actual_hash,
        }
        self._save_state()

        installed = InstalledExtension(
            manifest=manifest,
            install_dir=target_dir,
            state=default_state,
            is_trusted=prev_trusted or manifest.is_declarative,
            readme_content=readme_content,
            package_file=package,
        )
        return True, f"Successfully installed {manifest.name} v{manifest.version}", installed

    def uninstall_extension(self, extension_id: str) -> Tuple[bool, str]:
        """Uninstalls an extension by removing its directory and state."""
        ext_folder = self.extensions_dir / extension_id
        if ext_folder.exists():
            try:
                shutil.rmtree(ext_folder, ignore_errors=True)
            except Exception as exc:
                return False, f"Failed to delete extension directory: {exc}"

        if extension_id in self._state_data:
            del self._state_data[extension_id]
            self._save_state()

        return True, f"Extension '{extension_id}' uninstalled successfully."

    def set_extension_state(self, extension_id: str, state: ExtensionState) -> bool:
        if extension_id in self._state_data:
            self._state_data[extension_id]["state"] = state.value
            self._save_state()
            return True
        return False

    def set_extension_trusted(self, extension_id: str, trusted: bool) -> bool:
        if extension_id in self._state_data:
            self._state_data[extension_id]["is_trusted"] = trusted
            self._save_state()
            return True
        return False

    def list_installed(self) -> List[InstalledExtension]:
        """Discovers all installed extensions from disk and state."""
        results: List[InstalledExtension] = []
        if not self.extensions_dir.exists():
            return results

        # Iterate over extension directories
        for ext_id_dir in self.extensions_dir.iterdir():
            if not ext_id_dir.is_dir() or ext_id_dir.name == "__pycache__":
                continue
            ext_id = ext_id_dir.name

            # Look for version subdirectories or direct manifest
            version_dirs = [v for v in ext_id_dir.iterdir() if v.is_dir()]
            if version_dirs:
                # Use latest version folder
                target_version_dir = sorted(version_dirs, key=lambda d: d.name, reverse=True)[0]
            else:
                target_version_dir = ext_id_dir

            manifest_file = target_version_dir / "manifest.json"
            if not manifest_file.exists():
                continue

            valid, _, manifest = ManifestValidator.validate_file(manifest_file)
            if not valid or not manifest:
                continue

            state_info = self._state_data.get(ext_id, {})
            state_val = state_info.get("state", ExtensionState.INSTALLED.value)
            try:
                state = ExtensionState(state_val)
            except ValueError:
                state = ExtensionState.INSTALLED

            is_trusted = state_info.get("is_trusted", manifest.is_declarative)

            readme_content = ""
            for name in ("README.md", "readme.md", "README.txt"):
                r_path = target_version_dir / name
                if r_path.exists():
                    try:
                        readme_content = r_path.read_text(encoding="utf-8", errors="replace")
                        break
                    except Exception:
                        pass

            pkg_path_str = state_info.get("package_file")
            package_file = Path(pkg_path_str) if pkg_path_str else None

            results.append(
                InstalledExtension(
                    manifest=manifest,
                    install_dir=target_version_dir,
                    state=state,
                    is_trusted=is_trusted,
                    readme_content=readme_content,
                    package_file=package_file,
                )
            )

        return results

    @staticmethod
    def create_oaext_package(source_dir: Path, output_file: Path) -> Path:
        """
        Packs a folder into an .oaext (ZIP) archive with manifest.json, extension.py, README.md, etc.
        """
        source = Path(source_dir).resolve()
        out = Path(output_file).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)

        if not (source / "manifest.json").exists():
            raise ValueError(f"Source directory '{source}' must contain 'manifest.json'")

        with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(source):
                for file in files:
                    full_p = Path(root) / file
                    rel_p = full_p.relative_to(source)
                    # Exclude temp or bytecode files
                    if "__pycache__" in rel_p.parts or rel_p.name.endswith((".pyc", ".tmp")):
                        continue
                    zf.write(full_p, arcname=str(rel_p).replace("\\", "/"))

        return out

