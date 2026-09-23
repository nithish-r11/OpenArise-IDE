import os
import tempfile
from pathlib import Path
from app.project.scanner import ProjectScanner

def test_scanner_basic_files():
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        (temp_path / "main.py").write_text("print('hello')", encoding='utf-8')
        (temp_path / "test_main.py").write_text("def test_hello(): pass", encoding='utf-8')
        (temp_path / "requirements.txt").write_text("fastapi==0.100.0\npytest", encoding='utf-8')
        
        scanner = ProjectScanner(temp_dir)
        files, git_available = scanner.scan_files()
        
        assert len(files) == 3
        assert not git_available
        
        py_files = [f for f in files if f.file_type == 'py']
        assert len(py_files) == 2
        
        test_files = [f for f in files if f.is_test]
        assert len(test_files) == 1
        assert test_files[0].relative_path == "test_main.py"

def test_scanner_sensitive_files():
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        (temp_path / ".env").write_text("SECRET=123", encoding='utf-8')
        (temp_path / "key.pem").write_text("KEY", encoding='utf-8')
        (temp_path / "credentials.json").write_text("{}", encoding='utf-8')
        
        scanner = ProjectScanner(temp_dir)
        files, _ = scanner.scan_files()
        
        assert len(files) == 3
        for f in files:
            assert f.content_hash is None, f"Sensitive file {f.relative_path} should not be hashed"

def test_scanner_ignored_dirs():
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        (temp_path / ".git").mkdir()
        (temp_path / ".git" / "config").write_text("data", encoding='utf-8')
        (temp_path / "__pycache__").mkdir()
        (temp_path / "__pycache__" / "file.pyc").write_text("data", encoding='utf-8')
        (temp_path / "node_modules").mkdir()
        (temp_path / "node_modules" / "pkg").write_text("data", encoding='utf-8')
        (temp_path / "main.py").write_text("data", encoding='utf-8')
        
        scanner = ProjectScanner(temp_dir)
        files, git_available = scanner.scan_files()
        
        assert len(files) == 1
        assert files[0].relative_path == "main.py"
        assert git_available

def test_scanner_dependencies():
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        (temp_path / "requirements.txt").write_text("fastapi==0.100.0\npytest>=7.0", encoding='utf-8')
        (temp_path / "setup.py").write_text("install_requires=['django==4.0']", encoding='utf-8')
        
        scanner = ProjectScanner(temp_dir)
        deps = scanner.scan_dependencies()
        
        assert len(deps) == 3
        dep_names = {d.name for d in deps}
        assert "fastapi" in dep_names
        assert "pytest" in dep_names
        assert "django" in dep_names
