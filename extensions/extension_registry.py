"""
Configurable marketplace registry client for OpenArise IDE.
Supports online catalog retrieval, offline fallbacks, package downloads,
hash verification, and update checking.
"""

import json
import urllib.request
import urllib.error
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from extensions.models import (
    RegistryEntry,
    InstalledExtension,
    OPENARISE_VERSION,
)
from extensions.extension_manifest import parse_semver
from extensions.extension_security import ExtensionSecurity


DEFAULT_REGISTRY_URL = "https://marketplace.openarise.org/api/v1/catalog.json"


class ExtensionRegistryClient:
    """
    Communicates with the OpenArise Extension Marketplace registry.
    Handles online catalog syncing, offline caching, and package downloads.
    """

    def __init__(
        self,
        registry_url: str = DEFAULT_REGISTRY_URL,
        cache_dir: Optional[Path] = None,
        local_catalog_path: Optional[Path] = None,
    ):
        self.registry_url = registry_url
        if cache_dir is None:
            self.cache_dir = Path.home() / ".openarise" / "marketplace_cache"
        else:
            self.cache_dir = Path(cache_dir).resolve()

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.local_catalog_path = local_catalog_path
        self._cached_catalog: Dict[str, RegistryEntry] = {}

    def fetch_catalog(self, force_refresh: bool = False) -> Tuple[bool, str, List[RegistryEntry]]:
        """
        Fetches extension catalog. If offline or request fails, falls back gracefully to local/cached catalog.
        """
        # Try online if registry_url is an HTTP/HTTPS URL
        if self.registry_url.startswith(("http://", "https://")) and not force_refresh:
            try:
                req = urllib.request.Request(
                    self.registry_url,
                    headers={"User-Agent": f"OpenAriseIDE/{OPENARISE_VERSION}"}
                )
                with urllib.request.urlopen(req, timeout=5) as response:
                    raw_data = response.read().decode("utf-8")
                    catalog_json = json.loads(raw_data)
                    entries = self._parse_catalog_data(catalog_json)
                    # Cache successful download
                    cache_file = self.cache_dir / "catalog_cache.json"
                    cache_file.write_text(raw_data, encoding="utf-8")
                    self._cached_catalog = {e.id: e for e in entries}
                    return True, "Online catalog synchronized.", entries
            except (urllib.error.URLError, TimeoutError, OSError):
                # Offline fallback
                pass
            except Exception as exc:
                pass

        # Try cached catalog file
        cache_file = self.cache_dir / "catalog_cache.json"
        if cache_file.exists():
            try:
                catalog_json = json.loads(cache_file.read_text(encoding="utf-8"))
                entries = self._parse_catalog_data(catalog_json)
                self._cached_catalog = {e.id: e for e in entries}
                return True, "Loaded catalog from offline cache.", entries
            except Exception:
                pass

        # Try local catalog path if provided
        if self.local_catalog_path and Path(self.local_catalog_path).exists():
            try:
                catalog_json = json.loads(Path(self.local_catalog_path).read_text(encoding="utf-8"))
                entries = self._parse_catalog_data(catalog_json)
                self._cached_catalog = {e.id: e for e in entries}
                return True, "Loaded catalog from local built-in registry.", entries
            except Exception as exc:
                return False, f"Failed to parse local catalog: {exc}", []

        # Return empty list if no catalog available
        return False, "Unable to reach Extension Registry (offline) and no cached catalog found.", []

    def _parse_catalog_data(self, data: Dict) -> List[RegistryEntry]:
        entries: List[RegistryEntry] = []
        raw_list = data.get("extensions", []) if isinstance(data, dict) else data
        if isinstance(raw_list, list):
            for item in raw_list:
                if isinstance(item, dict) and "id" in item:
                    try:
                        entries.append(RegistryEntry.from_dict(item))
                    except Exception:
                        pass
        return entries

    def get_entry(self, extension_id: str) -> Optional[RegistryEntry]:
        return self._cached_catalog.get(extension_id)

    def check_updates(self, installed_extensions: List[InstalledExtension]) -> List[Tuple[InstalledExtension, RegistryEntry]]:
        """
        Compares installed extension versions with the registry catalog.
        Returns list of (InstalledExtension, newer_RegistryEntry).
        """
        updates_available: List[Tuple[InstalledExtension, RegistryEntry]] = []
        for installed in installed_extensions:
            entry = self._cached_catalog.get(installed.manifest.id)
            if not entry:
                continue
            try:
                inst_ver = parse_semver(installed.manifest.version)
                cat_ver = parse_semver(entry.version)
                if cat_ver > inst_ver:
                    updates_available.append((installed, entry))
            except ValueError:
                continue
        return updates_available

    def download_package(
        self,
        entry: RegistryEntry,
        target_dir: Optional[Path] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Tuple[bool, str, Optional[Path]]:
        """
        Downloads the .oaext package for entry, verifies SHA-256 hash.
        """
        dest_dir = target_dir or self.cache_dir / "downloads"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / f"{entry.id}-{entry.version}.oaext"

        url = entry.download_url

        # Check if download_url is a local file
        if url.startswith("file://") or Path(url).exists():
            local_path = Path(url.replace("file://", ""))
            if local_path.exists():
                import shutil
                shutil.copy2(local_path, dest_file)
            else:
                return False, f"Local package path not found: {url}", None
        else:
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": f"OpenAriseIDE/{OPENARISE_VERSION}"}
                )
                with urllib.request.urlopen(req, timeout=15) as response:
                    total_size = int(response.headers.get("content-length", 0))
                    downloaded = 0
                    with open(dest_file, "wb") as f:
                        while True:
                            chunk = response.read(65536)
                            if not chunk:
                                break
                            f.write(chunk)
                            downloaded += len(chunk)
                            if progress_callback:
                                progress_callback(downloaded, total_size)
            except Exception as exc:
                return False, f"Download failed: {exc}", None

        # Verify SHA-256
        if entry.package_hash:
            matches, actual = ExtensionSecurity.verify_package_hash(dest_file, entry.package_hash)
            if not matches:
                try:
                    dest_file.unlink()
                except OSError:
                    pass
                return False, f"Downloaded package hash mismatch (expected {entry.package_hash}, got {actual})", None

        return True, "Download and hash verification complete.", dest_file

