from app.context.manager import ContextManager

def test_context_manager():
    manager = ContextManager(project_root="/test/project")
    
    manager.update_request("Fix a bug")
    assert manager.user_request == "Fix a bug"
    
    manager.add_selected_file("main.py")
    assert "main.py" in manager.selected_files
    
    manager.add_relevant_code("main.py", "print('hello')")
    assert manager.relevant_code["main.py"] == "print('hello')"
    
    manager.add_terminal_output("Error: Something went wrong")
    assert len(manager.terminal_output) == 1
    
    summary = manager.get_context_summary()
    assert summary["user_request"] == "Fix a bug"
    assert summary["project_root"] == "/test/project"
    assert summary["code_snippets"] == 1
    assert summary["failures"] == 0
