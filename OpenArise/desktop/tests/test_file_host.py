import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
host_path = Path(__file__).resolve().parents[1] / "python" / "file_host.py"
spec = importlib.util.spec_from_file_location("desktop_file_host", host_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
FileHost, FileError = module.FileHost, module.FileError
from app.tools.permissions import PermissionManager, PermissionAction

class FileHostTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "main.py").write_text("print('hello')\n", encoding="utf8")
        self.host = FileHost(self.root)

    def test_real_read_and_save_reuses_existing_writer(self):
        before = self.host.read_file("main.py")
        with patch.object(self.host.writer, "execute", wraps=self.host.writer.execute) as writer:
            result = self.host.save_file({"path": "main.py", "revision": before["revision"], "content": "print('saved')\n"})
        writer.assert_called_once_with(path="main.py", content="print('saved')\n", overwrite=True)
        self.assertEqual(result["content"], "print('saved')\n")
        self.assertNotEqual(result["revision"], before["revision"])
        self.assertEqual(self.host.permissions._approvals, {})
        self.assertFalse(self.host.permissions.test_mode)

    def test_external_edit_rejected_without_write(self):
        before = self.host.read_file("main.py")
        (self.root / "main.py").write_text("external", encoding="utf8")
        with self.assertRaises(FileError) as error:
            self.host.save_file({"path": "main.py", "revision": before["revision"], "content": "mine"})
        self.assertEqual(error.exception.code, "conflict")
        self.assertEqual((self.root / "main.py").read_text(), "external")

    def test_unopened_save_rejected(self):
        with self.assertRaises(FileError):
            self.host.save_file({"path": "main.py", "revision": self.host.digest(self.root / "main.py"), "content": "pass"})

    def test_deny_policy_is_authoritative(self):
        before = self.host.read_file("main.py")
        with patch.object(self.host.permissions, "get_action_for_risk", return_value=PermissionAction.DENY):
            with self.assertRaises(FileError) as error:
                self.host.save_file({"path": "main.py", "revision": before["revision"], "content": "denied"})
        self.assertEqual(error.exception.code, "permission_required")
        self.assertEqual(self.host.permissions._approvals, {})
        self.assertIn("hello", (self.root / "main.py").read_text())

    def test_failed_write_revokes_permission(self):
        before = self.host.read_file("main.py")
        with patch.object(self.host.writer, "execute", side_effect=OSError("failed")):
            with self.assertRaises(OSError):
                self.host.save_file({"path": "main.py", "revision": before["revision"], "content": "pass"})
        self.assertEqual(self.host.permissions._approvals, {})

    def test_protected_paths_not_listed_or_readable(self):
        (self.root / ".env").write_text("private")
        (self.root / ".git").mkdir()
        (self.root / ".venv").mkdir()
        (self.root / "nested").mkdir()
        self.assertEqual([e["name"] for e in self.host.list_directory("")], ["nested", "main.py"])
        for path in ["../outside.py", ".env", ".git/config", ".venv/file.py", "C:/file.py"]:
            with self.subTest(path=path), self.assertRaises(FileError):
                self.host.read_file(path)

    def test_link_is_rejected(self):
        with patch.object(Path, "is_symlink", return_value=True):
            with self.assertRaises(FileError):
                self.host.read_file("main.py")

    def test_other_text_is_readonly(self):
        (self.root / "notes.md").write_text("notes", encoding="utf8")
        before = self.host.read_file("notes.md")
        self.assertTrue(before["readOnly"])
        with self.assertRaises(FileError):
            self.host.save_file({"path": "notes.md", "revision": before["revision"], "content": "new"})

    def test_binary_and_large_files_rejected(self):
        (self.root / "binary.py").write_bytes(b"a\x00b")
        with self.assertRaises(FileError):
            self.host.read_file("binary.py")
        (self.root / "large.py").write_bytes(b"x" * (module.MAX_BYTES + 1))
        with self.assertRaises(FileError):
            self.host.read_file("large.py")

    def test_observation_uses_existing_facade(self):
        observation = self.host.dispatch("observe", {})
        self.assertEqual(observation["files"], 1)
        self.assertEqual(observation["modules"], 1)
        self.assertTrue(observation["observedAt"])
        self.assertEqual(self.host.dispatch("shutdown", {}), {"closed": True})

    def test_unknown_operation_rejected(self):
        with self.assertRaises(FileError):
            self.host.dispatch("execute", {"command": "python main.py"})

    def test_run_requires_opened_current_revision(self):
        revision = self.host.digest(self.root / "main.py")
        with self.assertRaises(FileError):
            self.host.dispatch("validate_run", {"path": "main.py", "revision": revision})
        self.host.read_file("main.py")
        result = self.host.dispatch("validate_run", {"path": "main.py", "revision": revision})
        self.assertEqual(result["path"], str(self.root / "main.py"))
        (self.root / "main.py").write_text("print('external')")
        with self.assertRaises(FileError):
            self.host.dispatch("validate_run", {"path": "main.py", "revision": revision})

    def test_environment_missing_project_interpreter_has_no_fallback(self):
        (self.root / ".venv").mkdir()
        result = self.host.dispatch("environment", {})
        self.assertEqual(result["status"], "unavailable")
        self.assertIn(".venv", result["executable"])

    def test_environment_uses_existing_detector(self):
        from app.environment.detector import EnvironmentDetector
        with patch.object(EnvironmentDetector, "detect", wraps=EnvironmentDetector().detect) as detect:
            result = self.host.dispatch("environment", {})
        detect.assert_called_once_with(str(self.root))
        self.assertEqual(result["executable"], sys.executable)

    def test_run_denies_traversal_and_non_python(self):
        for path in ("../main.py", "/main.py", ".env", ".venv/test.py"):
            with self.assertRaises((FileError, FileNotFoundError)):
                self.host.dispatch("validate_run", {"path": path, "revision": "a" * 64})

if __name__ == "__main__":
    unittest.main()
