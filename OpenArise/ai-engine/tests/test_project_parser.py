import os
import tempfile
from pathlib import Path
from app.project.parser import PythonParser

def test_python_parser_valid_file():
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        file_path = temp_path / "valid.py"
        file_path.write_text("import os\nfrom typing import List\nclass TestClass:\n    def method(self):\n        pass\n\ndef test_method():\n    pass", encoding="utf-8")
        
        info = PythonParser.parse_file(str(file_path), "valid.py", "valid")
        
        assert info.syntax_error is None
        assert "os" in info.imports
        assert "typing" in info.imports
        assert "TestClass" in info.classes
        assert "method" in info.functions
        assert "test_method" in info.test_functions

def test_python_parser_syntax_error():
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        file_path = temp_path / "invalid.py"
        file_path.write_text("def method(:\n    pass", encoding="utf-8")
        
        info = PythonParser.parse_file(str(file_path), "invalid.py", "invalid")
        
        assert info.syntax_error is not None
        assert "SyntaxError" in info.syntax_error

def test_python_parser_missing_file():
    info = PythonParser.parse_file("doesnt_exist.py", "doesnt_exist.py", "doesnt_exist")
    assert info.syntax_error is not None
    assert "Failed to read file" in info.syntax_error
