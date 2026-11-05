"""
Security enforcement, ZIP path traversal prevention, SHA-256 verification,
and permissions handling for OpenArise IDE extensions.
"""

import hashlib
import os
import zipfile
from pathlib import Path
from typing import List, Optional, Tuple, Set

from extensions.models import ExtensionManifest, PERMISSION_DESCRIPTIONS


class SecurityException(Exception):
    """Raised when an extension package violates security constraints."""
    pass


class ExtensionSecurity:
    """
    Enforces security policies:
    - Rejects ZIP path traversal attacks
    - Computes and verifies SHA-256 hashes
    - Inspects requested permissions
    - Tracks user trust decisions for Python extensions
    """

    @staticmethod
    def calculate_sha256(file_path: Path) -> str:
        """Calculates the SHA-256 hex digest of a file."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest().lower()

    @classmethod
    def verify_package_hash(cls, package_path: Path, expected_hash: str) -> Tuple[bool, str]:
        """
        Verifies that package_path matches expected_hash.
        Returns (is_valid, calculated_hash).
        """
        if not expected_hash:
            return True, cls.calculate_sha256(package_path)
        actual = cls.calculate_sha256(package_path)
        return actual == expected_hash.strip().lower(), actual

    @staticmethod
    def safe_extract_zip(zip_path: Path, target_dir: Path) -> List[Path]:
        """
        Safely extracts all files from a ZIP archive, strictly preventing path traversal.
        Raises SecurityException if any entry attempts to write outside target_dir.
        """
        target_dir = target_dir.resolve()
        target_dir.mkdir(parents=True, exist_ok=True)
        extracted: List[Path] = []

        with zipfile.ZipFile(zip_path, "r") as zf:
            # First pass: validate all entries before extracting anything
            for member in zf.infolist():
                filename = member.filename
                # Disallow drive letters, absolute paths, and parent traversals
                if os.path.isabs(filename) or (len(filename) > 1 and filename[1] == ":"):
                    raise SecurityException(f"Illegal absolute path detected in package: '{filename}'")

                parts = Path(filename).parts
                if ".." in parts:
                    raise SecurityException(f"Path traversal ('..') detected in package member: '{filename}'")

                # Ensure resolved destination starts with target_dir
                dest = (target_dir / filename).resolve()
                try:
                    dest.relative_to(target_dir)
                except ValueError:
                    raise SecurityException(f"Package member extracts outside target directory: '{filename}'")

            # Second pass: safe extraction
            for member in zf.infolist():
                dest = (target_dir / member.filename).resolve()
                if member.is_dir():
                    dest.mkdir(parents=True, exist_ok=True)
                else:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member) as source, open(dest, "wb") as target:
                        for chunk in iter(lambda: source.read(65536), b""):
                            target.write(chunk)
                    extracted.append(dest)

        return extracted

    @staticmethod
    def inspect_permissions(manifest: ExtensionManifest) -> List[Tuple[str, str]]:
        """
        Returns list of (permission_name, description) requested by the extension.
        """
        results = []
        for perm in manifest.permissions:
            desc = PERMISSION_DESCRIPTIONS.get(perm, "Custom extension capability")
            results.append((perm, desc))
        return results

    @staticmethod
    def is_declarative_safe(manifest: ExtensionManifest) -> bool:
        """
        Returns True if extension is purely declarative (e.g. themes, snippets)
        and does not execute third-party Python code.
        """
        return manifest.is_declarative

