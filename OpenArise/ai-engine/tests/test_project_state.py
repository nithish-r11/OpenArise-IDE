import os
import tempfile
from pathlib import Path
from app.project.state import ProjectStateManager

def test_project_state_refresh():
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        (temp_path / "main.py").write_text("import fastapi\n\ndef main():\n    pass", encoding='utf-8')
        (temp_path / "test_main.py").write_text("import pytest\n\ndef test_main():\n    pass", encoding='utf-8')
        (temp_path / "requirements.txt").write_text("fastapi==0.100.0\npytest", encoding='utf-8')
        
        manager = ProjectStateManager(temp_dir)
        state = manager.refresh()
        
        assert state is not None
        assert state.project_info.root_path == str(temp_path.resolve())
        assert len(state.files) == 3
        
        assert len(state.python_modules) == 2
        
        assert len(state.dependencies) == 2
        
        assert "fastapi" in state.frameworks
        assert "pytest" in state.frameworks
        
        assert len(state.tests) == 1
        assert state.tests[0] == "test_main.py"
        
        assert not state.health_signals.get("empty_project")
        assert not state.health_signals.get("no_python_files")
        assert not state.health_signals.get("no_tests")
        assert not state.health_signals.get("syntax_errors")
        
        # Test cache hit on unchanged file
        state_again = manager.refresh()
        assert state_again.scan_timestamp != state.scan_timestamp
