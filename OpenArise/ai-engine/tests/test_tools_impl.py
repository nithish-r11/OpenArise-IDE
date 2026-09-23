import pytest
import os
import tempfile
import sys
from app.tools.inspector import ProjectInspectorTool
from app.tools.fs import ReadFileTool, WriteFileTool, EditFileTool
from app.tools.execution import PythonExecutionTool, TestExecutionTool

@pytest.fixture
def sandbox():
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create some files
        os.makedirs(os.path.join(temp_dir, "src"))
        with open(os.path.join(temp_dir, "src", "main.py"), "w") as f:
            f.write("print('Hello World')\n")
        with open(os.path.join(temp_dir, ".env"), "w") as f:
            f.write("SECRET=123\n")
        yield temp_dir

def test_inspector_tool(sandbox):
    tool = ProjectInspectorTool(project_root=sandbox)
    result = tool.execute()
    assert "src" in result["directories"]
    assert os.path.join("src", "main.py") in result["files"]

def test_read_file_tool(sandbox):
    tool = ReadFileTool(project_root=sandbox)
    
    # Successful read
    result = tool.execute(path="src/main.py")
    assert "Hello World" in result["content"]
    
    # Path traversal attempt
    with pytest.raises(ValueError):
        tool.execute(path="../outside.txt")
        
    # Sensitive file attempt
    with pytest.raises(ValueError):
        tool.execute(path=".env")

def test_write_file_tool(sandbox):
    tool = WriteFileTool(project_root=sandbox)
    
    # Successful write
    tool.execute(path="src/new.py", content="x = 1")
    assert os.path.exists(os.path.join(sandbox, "src", "new.py"))
    
    # Overwrite protection
    with pytest.raises(FileExistsError):
        tool.execute(path="src/new.py", content="x = 2")
        
    # Explicit overwrite
    tool.execute(path="src/new.py", content="x = 2", overwrite=True)
    with open(os.path.join(sandbox, "src", "new.py"), "r") as f:
        assert f.read() == "x = 2"

def test_edit_file_tool(sandbox):
    tool = EditFileTool(project_root=sandbox)
    
    # Exact match success
    tool.execute(path="src/main.py", old_text="Hello World", new_text="Hello Agent")
    with open(os.path.join(sandbox, "src", "main.py"), "r") as f:
        assert "Hello Agent" in f.read()
        
    # Ambiguous edit (mock a file with duplicates)
    with open(os.path.join(sandbox, "dup.txt"), "w") as f:
        f.write("foo foo")
    
    with pytest.raises(ValueError, match="Ambiguous edit"):
        tool.execute(path="dup.txt", old_text="foo", new_text="bar")
        
    # Not found
    with pytest.raises(ValueError, match="not found in file"):
        tool.execute(path="src/main.py", old_text="NonExistent", new_text="bar")

def test_python_execution_tool(sandbox):
    tool = PythonExecutionTool(project_root=sandbox)
    
    # Create an endless script to test timeout
    with open(os.path.join(sandbox, "timeout.py"), "w") as f:
        f.write("import time\nwhile True: time.sleep(1)")
        
    result = tool.execute(script_path="timeout.py", timeout=1)
    assert result["exit_code"] == -1
    assert result["error"] == "TimeoutExpired"
    
    # Normal execution
    result2 = tool.execute(script_path="src/main.py")
    assert result2["exit_code"] == 0
    assert "Hello World" in result2["stdout"]

def test_test_execution_tool(sandbox):
    # We will test running pytest on an empty directory (returns exit code 5 usually for no tests collected, but it successfully ran the command)
    tool = TestExecutionTool(project_root=sandbox)
    result = tool.execute()
    # Pytest returns 5 when no tests are collected
    assert result["exit_code"] == 5
    assert "pytest" in result["command"]
