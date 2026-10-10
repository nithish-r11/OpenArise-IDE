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
        (self.root / "notes.log").write_text("notes", encoding="utf8")
        before = self.host.read_file("notes.log")
        self.assertTrue(before["readOnly"])
        with self.assertRaises(FileError):
            self.host.save_file({"path": "notes.log", "revision": before["revision"], "content": "new"})

    def test_frontend_and_config_saving_has_the_same_conflict_guard(self):
        for name in ("App.tsx", "site.css", "package.json", "notes.md"):
            with self.subTest(name=name):
                (self.root / name).write_text("original", encoding="utf8")
                file = self.host.read_file(name)
                self.assertFalse(file["readOnly"])
                self.assertEqual(self.host.save_file({"path": name, "revision": file["revision"], "content": "edited"})["content"], "edited")
                with self.assertRaises(FileError):
                    self.host.save_file({"path": name, "revision": file["revision"], "content": "stale"})
                self.assertEqual((self.root / name).read_text(), "edited")

    def test_new_file_is_exclusive_and_permission_checked(self):
        result = self.host.create_file("new.tsx")
        self.assertEqual(result["content"], "")
        self.assertFalse(result["readOnly"])
        with self.assertRaises(FileError):
            self.host.create_file("new.tsx")
        with patch.object(self.host.permissions, "get_action_for_risk", return_value=PermissionAction.DENY):
            with self.assertRaises(FileError):
                self.host.create_file("denied.py")
        self.assertFalse((self.root / "denied.py").exists())
        self.assertEqual(self.host.permissions._approvals, {})

    def test_creation_rejects_protected_paths_and_missing_parent(self):
        for name in ("../outside.py", ".env", ".venv/new.py", ".openarise/new.py", "missing/new.py", "program.exe"):
            with self.subTest(name=name), self.assertRaises((FileError, FileNotFoundError)):
                self.host.create_file(name)

    def test_filename_search_is_project_scoped_and_excludes_secrets(self):
        (self.root / "frontend").mkdir()
        (self.root / "frontend" / "App.tsx").write_text("export const App = 1")
        (self.root / "secret_App.tsx").write_text("private")
        self.assertEqual(self.host.search_files("App.tsx"), [{"name": "App.tsx", "path": "frontend/App.tsx", "kind": "file"}])

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

class ExplorerMutationTests(unittest.TestCase):
    # Reuse fixture setup without running inherited tests twice.
    setUp = FileHostTests.setUp
    def test_windows_names_and_empty_components_are_rejected_in_the_host(self):
        for path in ("a//b", "a/./b", "NUL", "bad.", "bad ", "a/b?", "../outside"):
            with self.assertRaises(FileError): self.host.create_folder(path)
    def test_folder_creation_is_real_and_never_replaces_existing_path(self):
        self.host.create_folder("actual")
        self.assertTrue((self.root / "actual").is_dir())
        with self.assertRaises(FileError): self.host.create_folder("main.py")
        self.assertIn("hello", (self.root / "main.py").read_text())
        self.assertEqual(self.host.permissions._approvals, {})

    def test_folder_creation_denied_by_backend_policy(self):
        with patch.object(self.host.permissions, "get_action_for_risk", return_value=PermissionAction.DENY):
            with self.assertRaises(FileError): self.host.create_folder("denied")
        self.assertFalse((self.root / "denied").exists())

    def test_real_file_rename_preserves_bytes_and_invalidates_old_buffer(self):
        self.host.read_file("main.py")
        review = self.host.inspect_rename("main.py")
        self.host.rename_path({"path": "main.py", "destination": "renamed.py", "revision": review["revision"]})
        self.assertFalse((self.root / "main.py").exists())
        self.assertIn("hello", (self.root / "renamed.py").read_text())
        self.assertNotIn("main.py", self.host.opened)

    def test_rename_conflicts_preserve_both_files(self):
        review = self.host.inspect_rename("main.py")
        (self.root / "existing.py").write_text("existing")
        with self.assertRaises(FileError): self.host.rename_path({"path": "main.py", "destination": "existing.py", "revision": review["revision"]})
        (self.root / "main.py").write_text("external")
        with self.assertRaises(FileError): self.host.rename_path({"path": "main.py", "destination": "fresh.py", "revision": review["revision"]})
        self.assertEqual((self.root / "existing.py").read_text(), "existing")
        self.assertFalse((self.root / "fresh.py").exists())

    def test_nonempty_folder_rename_checks_all_descendants(self):
        self.host.create_folder("source")
        (self.root / "source/a.ts").write_text("export const a=1;")
        review = self.host.inspect_rename("source")
        self.host.rename_path({"path": "source", "destination": "destination", "revision": review["revision"]})
        self.assertEqual((self.root / "destination/a.ts").read_text(), "export const a=1;")

    def test_rename_rejects_protected_descendants_and_deny_policy(self):
        self.host.create_folder("source"); (self.root / "source/.env").write_text("private")
        with self.assertRaises(FileError): self.host.inspect_rename("source")
        review = self.host.inspect_rename("main.py")
        with patch.object(self.host.permissions, "get_action_for_risk", return_value=PermissionAction.DENY):
            with self.assertRaises(FileError): self.host.rename_path({"path": "main.py", "destination": "denied.py", "revision": review["revision"]})
        self.assertTrue((self.root / "main.py").exists())
        self.assertEqual(self.host.permissions._approvals, {})

if __name__ == "__main__":
    unittest.main()
