import json
import os
import shutil
import time
from pathlib import Path
from typing import Optional, Dict, Any, List


class RecoveryManager:
    """
    Manages session crash recovery for OpenArise IDE.
    Stores unsaved editor buffers, cursor positions, tab ordering, and clean exit status.
    """

    def __init__(self, recovery_dir: Optional[Path] = None):
        if recovery_dir is None:
            self.recovery_dir = Path.home() / ".openarise" / "recovery"
        else:
            self.recovery_dir = Path(recovery_dir)
        self.meta_file = self.recovery_dir / "recovery_metadata.json"
        self.snapshots_dir = self.recovery_dir / "snapshots"
        self._crashed_session: Optional[Dict[str, Any]] = self._inspect_for_crash()

    def _inspect_for_crash(self) -> Optional[Dict[str, Any]]:
        """
        Inspects on startup before new session writes. Captures crashed session in memory.
        """
        if not self.meta_file.exists():
            return None
        try:
            meta = json.loads(self.meta_file.read_text(encoding="utf-8"))
            if meta.get("clean_exit") is False and meta.get("tabs"):
                restored_tabs = []
                for tab in meta.get("tabs", []):
                    snap_file = self.snapshots_dir / tab.get("snapshot_file", "")
                    content = ""
                    if snap_file.exists():
                        content = snap_file.read_text(encoding="utf-8", errors="replace")
                    restored_tabs.append({
                        "tab_name": tab.get("tab_name"),
                        "file_path": tab.get("file_path") or None,
                        "is_modified": tab.get("is_modified", False),
                        "cursor_position": tab.get("cursor_position", 0),
                        "content": content,
                    })
                return {
                    "project_root": meta.get("project_root") or None,
                    "timestamp": meta.get("timestamp", 0),
                    "tabs": restored_tabs,
                }
        except Exception:
            pass
        return None

    def start_session(self, project_root: Optional[Path] = None):
        """
        Called when MainWindow starts up. Marks clean_exit=False to track session health.
        """
        try:
            self.recovery_dir.mkdir(parents=True, exist_ok=True)
            self.snapshots_dir.mkdir(parents=True, exist_ok=True)
            meta = {
                "clean_exit": False,
                "timestamp": time.time(),
                "project_root": str(project_root) if project_root else "",
                "tabs": [],
            }
            self.meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        except Exception:
            pass

    def save_snapshot(self, project_root: Optional[Path], tabs_info: List[Dict[str, Any]]):
        """
        Saves a snapshot of currently open tabs, cursor positions, and buffer contents.
        tabs_info item: {
            'tab_name': str,
            'file_path': str or None,
            'is_modified': bool,
            'cursor_position': int,
            'content': str
        }
        """
        try:
            self.snapshots_dir.mkdir(parents=True, exist_ok=True)
            # Remove old snapshot text files
            for old in self.snapshots_dir.glob("tab_*.txt"):
                try:
                    old.unlink()
                except OSError:
                    pass

            serialized_tabs = []
            for i, tab in enumerate(tabs_info):
                snap_filename = f"tab_{i}.txt"
                snap_path = self.snapshots_dir / snap_filename
                snap_path.write_text(tab.get("content", ""), encoding="utf-8", errors="replace")
                serialized_tabs.append({
                    "tab_name": tab.get("tab_name", "Untitled"),
                    "file_path": tab.get("file_path") or "",
                    "is_modified": tab.get("is_modified", False),
                    "cursor_position": tab.get("cursor_position", 0),
                    "snapshot_file": snap_filename,
                })

            meta = {
                "clean_exit": False,
                "timestamp": time.time(),
                "project_root": str(project_root) if project_root else "",
                "tabs": serialized_tabs,
            }
            temp_meta = self.recovery_dir / "recovery_metadata.json.tmp"
            temp_meta.write_text(json.dumps(meta, indent=2), encoding="utf-8")
            temp_meta.replace(self.meta_file)
        except Exception:
            pass

    def has_recoverable_session(self) -> bool:
        """
        Returns True if an unexpected shutdown occurred and there is unsaved/open session data.
        """
        if self._crashed_session and self._crashed_session.get("tabs"):
            return True
        if not self.meta_file.exists():
            return False
        try:
            meta = json.loads(self.meta_file.read_text(encoding="utf-8"))
            if meta.get("clean_exit") is False and meta.get("tabs"):
                return True
        except Exception:
            pass
        return False

    def get_recovered_session(self) -> Optional[Dict[str, Any]]:
        """
        Loads recovered session metadata and reads buffer contents from snapshot files.
        """
        if self._crashed_session:
            return self._crashed_session
        return self._inspect_for_crash()

    def mark_recovery_handled(self):
        """
        Called after user restores or chooses action so pending crash state is cleared.
        """
        self._crashed_session = None

    def mark_clean_exit(self):
        """
        Marks clean_exit=True and removes recovery data on clean application shutdown.
        """
        try:
            if self.meta_file.exists():
                meta = {"clean_exit": True, "timestamp": time.time(), "tabs": []}
                self.meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")
            if self.snapshots_dir.exists():
                shutil.rmtree(self.snapshots_dir, ignore_errors=True)
        except Exception:
            pass

    def clear_recovery(self):
        """
        Removes all recovery files when user discards a recovered session.
        """
        self._crashed_session = None
        try:
            if self.recovery_dir.exists():
                shutil.rmtree(self.recovery_dir, ignore_errors=True)
        except Exception:
            pass
