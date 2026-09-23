import os
import tempfile
from pathlib import Path
from app.project.registry import ProjectRegistry

def test_project_registry():
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        (temp_path / "main.py").write_text("print('hello')", encoding='utf-8')
        
        registry = ProjectRegistry()
        
        pid1 = registry.register_project(temp_dir)
        assert pid1 is not None
        
        # Registering again should return the same stable ID
        pid2 = registry.register_project(temp_dir)
        assert pid1 == pid2
        
        state = registry.get_project(pid1)
        assert state is not None
        assert state.project_info.root_path == str(temp_path.resolve())
        
        projects = registry.list_projects()
        assert len(projects) == 1
        assert projects[0] == pid1
        
        closed = registry.close_project(pid1)
        assert closed
        
        assert registry.get_project(pid1) is None
        assert len(registry.list_projects()) == 0
