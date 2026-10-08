"""Fingerprint source, tests and configuration without exposing file content."""
import hashlib
import json
from app.project.scanner import ProjectScanner
from app.tools.fs import _is_safe_path

def project_snapshot(root):
    try:
        files, _ = ProjectScanner(root).scan_files()
        facts = {}
        for item in files:
            if item.is_source or item.is_test or item.is_config:
                if not _is_safe_path(root, item.relative_path) or not item.content_hash:
                    return None
                facts[item.relative_path] = item.content_hash
        return hashlib.sha256(json.dumps(facts, sort_keys=True).encode()).hexdigest()
    except (OSError, ValueError):
        return None
