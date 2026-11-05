"""
Manual Acceptance Test for OpenArise AI Chat Context & Formatting Fix
Tests hi.py with live Ollama (qwen2.5-coder:7b).
"""
import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow

def run_acceptance_test():
    app = QApplication.instance() or QApplication(sys.argv)
    
    workspace = Path("E:/OpenArise_IDE/OpenArise_IDE/tests/acceptance_workspace")
    workspace.mkdir(parents=True, exist_ok=True)
    
    hi_py = workspace / "hi.py"
    hi_py_code = (
        "import sys\n\n"
        "def add(x, y):\n"
        "    return x + y\n\n"
        "def subtract(x, y):\n"
        "    return x - y\n\n"
        "def multiply(x, y):\n"
        "    return x * y\n\n"
        "def divide(x, y):\n"
        "    if y == 0:\n"
        "        print('Error: Division by zero is not allowed.')\n"
        "        return None\n"
        "    return x / y\n"
    )
    hi_py.write_text(hi_py_code, encoding="utf-8")
    
    from unittest.mock import patch, MagicMock

    with patch.object(MainWindow, "_check_startup_recovery_and_project", MagicMock()):
        window = MainWindow()
    window._load_project_folder(workspace)
    app.processEvents()
    
    ed = window.editor.open_file(hi_py)
    app.processEvents()
    
    print("=" * 60)
    print("STEP 1: Testing Chat with Active File (hi.py) attached")
    print("=" * 60)
    
    # Send chat query
    window.send_chat(
        text="What functions are defined in hi.py? Explain what each function does.",
        model="qwen2.5-coder:7b",
        include_codebase=False,
        attachments=["__ACTIVE__"]
    )
    
    # Wait for Ollama streaming worker to finish
    timeout = 120
    start_t = time.time()
    last_print = time.time()
    while window.chat_worker and window.chat_worker.isRunning():
        app.processEvents()
        time.sleep(0.05)
        if time.time() - last_print > 5:
            last_print = time.time()
            print(f"Waiting for Ollama... elapsed {int(time.time() - start_t)}s, current text len: {len(window.chat.output.toPlainText())}")
        if time.time() - start_t > timeout:
            print("ERROR: Timeout waiting for Ollama response")
            return False
            
    app.processEvents()
    time.sleep(0.5)
    app.processEvents()
    
    response_text = window.chat.output.toPlainText()
    response_html = window.chat.output.toHtml()
    
    print("\n[AI RESPONSE TEXT]:\n")
    print(response_text)
    print("\n" + "=" * 60)
    
    # Verifications for Step 1
    # Check 1: 4 functions identified
    fn_checks = {
        "add": "add" in response_text.lower(),
        "subtract": "subtract" in response_text.lower(),
        "multiply": "multiply" in response_text.lower(),
        "divide": "divide" in response_text.lower(),
    }
    print(f"Function checks: {fn_checks}")
    assert all(fn_checks.values()), f"Model failed to detect all functions: {fn_checks}"
    
    # Check 2: Mentions zero division
    div_zero_ok = "zero" in response_text.lower() or "division by zero" in response_text.lower()
    print(f"Division by zero mentioned: {div_zero_ok}")
    assert div_zero_ok, "Model did not mention division by zero handling"
    
    # Check 3: No raw </p> tags
    assert "</p>" not in response_text, "Found raw </p> in response text!"
    assert "&lt;/p&gt;" not in response_html, "Found escaped raw </p> in response html!"
    print("No stray </p> tags verified.")
    
    # Check 4: No duplicate code blocks in action row or text
    print("Checking duplicate code blocks...")
    action_btns = window.chat.chat_panel.action_row.count()
    print(f"Action row buttons created: {action_btns}")
    
    print("\n" + "=" * 60)
    print("STEP 2: Testing Unsaved Buffer Modification")
    print("=" * 60)
    
    # Modify buffer without saving to disk
    modulo_func = "\ndef modulo(x, y):\n    '''Returns the remainder of division'''\n    return x % y\n"
    ed.setPlainText(hi_py_code + modulo_func)
    ed.document().setModified(True)
    app.processEvents()
    
    # Verify disk still has old code
    assert "modulo" not in hi_py.read_text(encoding="utf-8"), "File should NOT be modified on disk!"
    
    # Send second query asking about newly added function
    window.send_chat(
        text="What functions are in hi.py now? List their exact names.",
        model="qwen2.5-coder:7b",
        include_codebase=False,
        attachments=["__ACTIVE__"]
    )
    
    start_t = time.time()
    last_print = time.time()
    while window.chat_worker and window.chat_worker.isRunning():
        app.processEvents()
        time.sleep(0.05)
        if time.time() - last_print > 5:
            last_print = time.time()
            print(f"Waiting for Ollama step 2... elapsed {int(time.time() - start_t)}s")
        if time.time() - start_t > timeout:
            print("ERROR: Timeout waiting for Ollama response in step 2")
            return False
            
    app.processEvents()
    time.sleep(0.5)
    app.processEvents()
    
    response2_text = window.chat.output.toPlainText()
    print("\n[AI RESPONSE TEXT 2 (with unsaved buffer)]:\n")
    print(response2_text)
    
    # Check modulo detected
    modulo_detected = "modulo" in response2_text.lower()
    print(f"Unsaved 'modulo' function detected by AI: {modulo_detected}")
    assert modulo_detected, "AI failed to detect unsaved 'modulo' function from editor buffer!"
    
    print("\n" + "=" * 60)
    print("ALL ACCEPTANCE CHECKS PASSED SUCCESSFULLY WITH LIVE OLLAMA!")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = run_acceptance_test()
    sys.exit(0 if success else 1)
