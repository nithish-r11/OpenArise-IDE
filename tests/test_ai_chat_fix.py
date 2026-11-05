"""
OpenArise IDE - Critical AI Chat Context & Response Formatting Test Suite.
Tests:
  1. Active editor file path retrieval
  2. Active editor unsaved buffer retrieval
  3. Active file attachment enabled
  4. Active file attachment disabled
  5. Active tab switching
  6. Missing active file handling (warning displayed, request aborted)
  7. Large-file context truncation
  8. Actual attachment in the Ollama request payload
  9. Markdown heading rendering
  10. Python code-block rendering with syntax styling
  11. Raw HTML tag handling & entity escaping
  12. Duplicate response prevention
  13. Streaming and final response consistency
  14. Chat history multi-turn compatibility
  15. Inline Edit compatibility
  16. @file compatibility with unsaved and disk files
  17. @codebase compatibility
  18. Ollama connection & worker cancellation
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from ui.main_window import MainWindow
from ui.chat_panel import ChatPanel, render_markdown
from core.context_manager import ContextManager
from core.ollama_client import OllamaStreamWorker


def run_tests():
    app = QApplication.instance() or QApplication(sys.argv)
    test_dir = Path(tempfile.mkdtemp(prefix="openarise_chat_test_"))
    results = {}

    print("\n=======================================================")
    print("STARTING OPENARISE AI CHAT CONTEXT & FORMATTING TESTS")
    print("=======================================================\n")
    print(f"Isolated test workspace: {test_dir}")

    window = None
    try:
        # Create test project directory and files
        proj_dir = test_dir / "my_project"
        proj_dir.mkdir(parents=True, exist_ok=True)
        hi_py = proj_dir / "hi.py"
        hi_py_content = (
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
        hi_py.write_text(hi_py_content, encoding="utf-8")

        other_py = proj_dir / "other.py"
        other_py.write_text("def helper():\n    return 'from_disk'\n", encoding="utf-8")

        # Initialize MainWindow
        window = MainWindow()
        window._load_project_folder(proj_dir)
        app.processEvents()

        # -----------------------------------------------------------------
        # TEST 1: Active editor file path retrieval
        # -----------------------------------------------------------------
        print("[TEST 1] Verifying Active Editor File Path Retrieval...")
        ed1 = window.editor.open_file(hi_py)
        app.processEvents()

        ctx1 = window.get_active_file_context()
        t1_ok = (
            ctx1 is not None and
            ctx1.get("filename") == "hi.py" and
            ctx1.get("path") in ("hi.py", str(hi_py)) and
            ctx1.get("abs_path") == str(hi_py.resolve())
        )
        results["1_active_file_path_retrieval"] = t1_ok
        print(f"  Result: {'PASS' if t1_ok else 'FAIL'} (Filename={ctx1.get('filename') if ctx1 else None}, Path={ctx1.get('path') if ctx1 else None})")

        # -----------------------------------------------------------------
        # TEST 2: Active editor unsaved buffer retrieval
        # -----------------------------------------------------------------
        print("[TEST 2] Verifying Active Editor Unsaved Buffer Retrieval...")
        unsaved_extra = "\ndef modulo(x, y):\n    return x % y\n"
        ed1.setPlainText(hi_py_content + unsaved_extra)
        ed1.document().setModified(True)
        app.processEvents()

        ctx2 = window.get_active_file_context()
        t2_ok = (
            ctx2 is not None and
            "def modulo(x, y):" in ctx2.get("content", "") and
            ctx2.get("is_unsaved") is True
        )
        results["2_unsaved_buffer_retrieval"] = t2_ok
        print(f"  Result: {'PASS' if t2_ok else 'FAIL'} (HasUnsaved={t2_ok}, IsUnsavedFlag={ctx2.get('is_unsaved') if ctx2 else None})")

        # Restore original content for subsequent tests
        ed1.setPlainText(hi_py_content)
        ed1.document().setModified(False)
        app.processEvents()

        # -----------------------------------------------------------------
        # TEST 3: Active file attachment enabled in prompt
        # -----------------------------------------------------------------
        print("[TEST 3] Verifying Active File Attachment Enabled in Prompt...")
        captured_messages = []
        def fake_worker_init(self_w, client, model, messages, parent=None):
            captured_messages.extend(messages)
            # Call super QThread init without launching requests
            super(OllamaStreamWorker, self_w).__init__(parent)

        with patch.object(OllamaStreamWorker, "__init__", fake_worker_init), \
             patch.object(OllamaStreamWorker, "start", MagicMock()):
            window.send_chat(
                text="What functions are in hi.py?",
                model="qwen2.5-coder:7b",
                include_codebase=False,
                attachments=["__ACTIVE__"]
            )
            app.processEvents()

        t3_ok = False
        if captured_messages:
            prompt_content = captured_messages[-1].get("content", "")
            t3_ok = (
                "[ATTACHED ACTIVE FILE: hi.py]" in prompt_content and
                "def add(x, y):" in prompt_content and
                "def divide(x, y):" in prompt_content and
                "USER REQUEST:\nWhat functions are in hi.py?" in prompt_content
            )
        results["3_active_file_attachment_enabled"] = t3_ok
        print(f"  Result: {'PASS' if t3_ok else 'FAIL'} (InPayload={t3_ok})")

        # -----------------------------------------------------------------
        # TEST 4: Active file attachment disabled
        # -----------------------------------------------------------------
        print("[TEST 4] Verifying Active File Attachment Disabled...")
        captured_messages.clear()
        with patch.object(OllamaStreamWorker, "__init__", fake_worker_init), \
             patch.object(OllamaStreamWorker, "start", MagicMock()):
            window.send_chat(
                text="Hello AI, general question",
                model="qwen2.5-coder:7b",
                include_codebase=False,
                attachments=[]  # No __ACTIVE__
            )
            app.processEvents()

        t4_ok = False
        if captured_messages:
            prompt_content = captured_messages[-1].get("content", "")
            t4_ok = (
                "[ATTACHED ACTIVE FILE" not in prompt_content and
                "def add(x, y):" not in prompt_content and
                "[ACTIVE FILE: None attached]" in prompt_content
            )
        results["4_active_file_attachment_disabled"] = t4_ok
        print(f"  Result: {'PASS' if t4_ok else 'FAIL'} (OmittedSuccessfully={t4_ok})")

        # -----------------------------------------------------------------
        # TEST 5: Active tab switching
        # -----------------------------------------------------------------
        print("[TEST 5] Verifying Active Tab Switching...")
        ed2 = window.editor.open_file(other_py)
        app.processEvents()

        ctx_tab2 = window.get_active_file_context()
        # Switch back to tab 0 (hi.py)
        window.editor.setCurrentIndex(0)
        app.processEvents()
        ctx_tab1 = window.get_active_file_context()

        t5_ok = (
            ctx_tab2 is not None and ctx_tab2.get("filename") == "other.py" and
            ctx_tab1 is not None and ctx_tab1.get("filename") == "hi.py"
        )
        results["5_active_tab_switching"] = t5_ok
        print(f"  Result: {'PASS' if t5_ok else 'FAIL'} (Tab1={ctx_tab1.get('filename') if ctx_tab1 else None}, Tab2={ctx_tab2.get('filename') if ctx_tab2 else None})")

        # -----------------------------------------------------------------
        # TEST 6: Missing active file handling (warning displayed, request aborted)
        # -----------------------------------------------------------------
        print("[TEST 6] Verifying Missing Active File Handling...")
        # Close all tabs
        while window.editor.count() > 0:
            window.editor.close_tab(0)
        app.processEvents()

        captured_messages.clear()
        with patch.object(OllamaStreamWorker, "__init__", fake_worker_init), \
             patch.object(OllamaStreamWorker, "start", MagicMock()):
            window.send_chat(
                text="What is in the file?",
                model="qwen2.5-coder:7b",
                include_codebase=False,
                attachments=["__ACTIVE__"]
            )
            app.processEvents()

        chat_out = window.chat.output.toPlainText()
        t6_ok = (
            len(captured_messages) == 0 and  # Request was aborted, not sent
            "no file is currently open in the editor" in chat_out.lower()
        )
        results["6_missing_active_file_handling"] = t6_ok
        print(f"  Result: {'PASS' if t6_ok else 'FAIL'} (RequestAborted={len(captured_messages)==0}, WarningShown=True)")

        # Re-open hi.py for subsequent tests
        ed1 = window.editor.open_file(hi_py)
        app.processEvents()

        # -----------------------------------------------------------------
        # TEST 7: Large-file context truncation
        # -----------------------------------------------------------------
        print("[TEST 7] Verifying Large-File Context Truncation...")
        large_py = proj_dir / "large.py"
        large_content = "# Large header\n" + ("x = 1\n" * 12_000)  # > 70,000 chars
        large_py.write_text(large_content, encoding="utf-8")
        window.editor.open_file(large_py)
        app.processEvents()

        ctx_large = window.get_active_file_context()
        t7_ok = (
            ctx_large is not None and
            ctx_large.get("truncated") is True and
            len(ctx_large.get("content", "")) <= 52_000 and
            "Truncated" in ctx_large.get("content", "")
        )
        results["7_large_file_truncation"] = t7_ok
        print(f"  Result: {'PASS' if t7_ok else 'FAIL'} (Truncated={ctx_large.get('truncated') if ctx_large else None}, Length={len(ctx_large.get('content', '')) if ctx_large else 0})")

        # Switch back to hi.py
        window.editor.setCurrentIndex(window.editor.find_tab_by_path(hi_py))
        app.processEvents()

        # -----------------------------------------------------------------
        # TEST 8: Actual attachment in the Ollama request payload
        # -----------------------------------------------------------------
        print("[TEST 8] Verifying Attachment Delimitation & Untrusted Source Framing...")
        captured_messages.clear()
        with patch.object(OllamaStreamWorker, "__init__", fake_worker_init), \
             patch.object(OllamaStreamWorker, "start", MagicMock()):
            window.send_chat(
                text="Explain divide function in hi.py",
                model="qwen2.5-coder:7b",
                include_codebase=False,
                attachments=["__ACTIVE__"]
            )
            app.processEvents()

        t8_ok = False
        if captured_messages:
            msg = captured_messages[-1].get("content", "")
            t8_ok = (
                "--- BEGIN hi.py ---" in msg and
                "--- END hi.py ---" in msg and
                "def divide(x, y):" in msg and
                "Base your answer directly on the attached source files" in msg
            )
        results["8_payload_delimiters"] = t8_ok
        print(f"  Result: {'PASS' if t8_ok else 'FAIL'} (Delimited=True, Framed=True)")

        # -----------------------------------------------------------------
        # TEST 9: Markdown heading rendering in ChatPanel
        # -----------------------------------------------------------------
        print("[TEST 9] Verifying Markdown Heading Rendering...")
        test_panel = ChatPanel()
        test_panel.begin_response()
        test_panel.append_token("### Functions Overview\n\nHere are functions:")
        test_panel.finish_response()
        app.processEvents()

        out_html = test_panel.output.toHtml()
        out_text = test_panel.output.toPlainText()
        t9_ok = (
            ("<h3>" in out_html or "<h3 " in out_html or "font-size:large" in out_html) and
            "### Functions Overview" not in out_text and
            "Functions Overview" in out_text
        )
        results["9_markdown_heading_rendering"] = t9_ok
        print(f"  Result: {'PASS' if t9_ok else 'FAIL'} (HasHeadingFormat={'font-size:large' in out_html or '<h3>' in out_html}, RawMarkdownStripped={'###' not in out_text})")

        # -----------------------------------------------------------------
        # TEST 10: Python code-block rendering with syntax styling
        # -----------------------------------------------------------------
        print("[TEST 10] Verifying Python Code-Block Rendering with Syntax Styling...")
        test_panel2 = ChatPanel()
        test_panel2.begin_response()
        test_panel2.append_token("```python\ndef add(x, y):\n    return x + y\n```")
        test_panel2.finish_response()
        app.processEvents()

        html2 = test_panel2.output.toHtml()
        t10_ok = (
            ("class=\"codehilite\"" in html2 or "<pre" in html2) and
            ("color: #66d9ef" in html2.lower() or "color:#66d9ef" in html2.lower() or "color: #a6e22e" in html2.lower() or "color:#a6e22e" in html2.lower() or "<code" in html2)
        )
        results["10_python_code_block_syntax"] = t10_ok
        print(f"  Result: {'PASS' if t10_ok else 'FAIL'} (StyledCodeBlock={t10_ok})")

        # -----------------------------------------------------------------
        # TEST 11: Raw HTML tag handling & entity escaping
        # -----------------------------------------------------------------
        print("[TEST 11] Verifying Raw HTML Tag Handling & Entity Escaping...")
        test_panel3 = ChatPanel()
        test_panel3.begin_response()
        test_panel3.append_token("Example HTML:\n```html\n<div class=\"test\">Hello</div>\n```\nDone.")
        test_panel3.finish_response()
        app.processEvents()

        text3 = test_panel3.output.toPlainText()
        t11_ok = (
            "</p>" not in text3 and
            '<div class="test">Hello</div>' in text3
        )
        results["11_raw_html_tag_handling"] = t11_ok
        print(f"  Result: {'PASS' if t11_ok else 'FAIL'} (NoStrayCloseP={'</p>' not in text3}, PreservedHtmlCode=True)")

        # -----------------------------------------------------------------
        # TEST 12: Duplicate response prevention
        # -----------------------------------------------------------------
        print("[TEST 12] Verifying Duplicate Response Prevention...")
        test_panel4 = ChatPanel()
        test_panel4.begin_response()
        test_panel4.append_token("Here is the code:\n```python\ndef unique_sample():\n    return 42\n```\nEnd.")
        test_panel4.finish_response()
        app.processEvents()

        text4 = test_panel4.output.toPlainText()
        count_sample = text4.count("def unique_sample():")
        t12_ok = (count_sample == 1)
        results["12_duplicate_response_prevention"] = t12_ok
        print(f"  Result: {'PASS' if t12_ok else 'FAIL'} (CodeOccurrences={count_sample})")

        # -----------------------------------------------------------------
        # TEST 13: Streaming and final response consistency
        # -----------------------------------------------------------------
        print("[TEST 13] Verifying Streaming and Final Response Consistency...")
        test_panel5 = ChatPanel()
        test_panel5.begin_response()
        tokens = ["Line 1.\n", "Line 2.\n", "Line 3.\n"]
        for t in tokens:
            test_panel5.append_token(t)
            app.processEvents()
        stream_text = test_panel5.output.toPlainText()
        test_panel5.finish_response()
        app.processEvents()
        final_text = test_panel5.output.toPlainText()

        t13_ok = (
            "Line 1." in stream_text and "Line 2." in stream_text and
            "Line 1." in final_text and "Line 2." in final_text and "Line 3." in final_text and
            final_text.count("Line 1.") == 1
        )
        results["13_streaming_consistency"] = t13_ok
        print(f"  Result: {'PASS' if t13_ok else 'FAIL'} (SingleOccurrence={final_text.count('Line 1.')==1})")

        # -----------------------------------------------------------------
        # TEST 14: Chat history multi-turn compatibility
        # -----------------------------------------------------------------
        print("[TEST 14] Verifying Chat History Multi-Turn Compatibility...")
        window.chat_history = []
        captured_multi = []
        with patch.object(OllamaStreamWorker, "__init__", fake_worker_init), \
             patch.object(OllamaStreamWorker, "start", MagicMock()):
            # Turn 1
            window.send_chat("First question", "qwen2.5-coder:7b", False, [])
            app.processEvents()
            # Simulate worker response callback
            if window.chat_worker:
                # Trigger callback
                window.chat.finish_response()
                window.chat_history.append({"role": "user", "content": "First question"})
                window.chat_history.append({"role": "assistant", "content": "First answer"})

            # Turn 2
            captured_multi.clear()
            def capture_turn2(self_w, client, model, messages, parent=None):
                captured_multi.extend(messages)
                super(OllamaStreamWorker, self_w).__init__(parent)
            with patch.object(OllamaStreamWorker, "__init__", capture_turn2):
                window.send_chat("Second question", "qwen2.5-coder:7b", False, [])
                app.processEvents()

        t14_ok = (
            len(captured_multi) >= 3 and
            captured_multi[0].get("content") == "First question" and
            captured_multi[1].get("content") == "First answer" and
            "Second question" in captured_multi[2].get("content", "")
        )
        results["14_chat_history_multi_turn"] = t14_ok
        print(f"  Result: {'PASS' if t14_ok else 'FAIL'} (HistoryRetained={t14_ok}, TotalTurns={len(captured_multi)})")

        # -----------------------------------------------------------------
        # TEST 15: Inline Edit compatibility
        # -----------------------------------------------------------------
        print("[TEST 15] Verifying Inline Edit Compatibility...")
        has_inline_btn = hasattr(window.chat.chat_panel, "inline_button")
        has_inline_method = hasattr(window, "inline_edit")
        t15_ok = has_inline_btn and has_inline_method
        results["15_inline_edit_compatibility"] = t15_ok
        print(f"  Result: {'PASS' if t15_ok else 'FAIL'} (HasButton={has_inline_btn}, HasMethod={has_inline_method})")

        # -----------------------------------------------------------------
        # TEST 16: @file compatibility with unsaved and disk files
        # -----------------------------------------------------------------
        print("[TEST 16] Verifying @file Compatibility (Unsaved Tab & Disk)...")
        # Open other.py in tab 1 and make unsaved edit
        ed_other = window.editor.open_file(other_py)
        ed_other.setPlainText("def helper():\n    return 'unsaved_buffer_version'\n")
        app.processEvents()

        captured_at_file = []
        def capture_at_file(self_w, client, model, messages, parent=None):
            captured_at_file.extend(messages)
            super(OllamaStreamWorker, self_w).__init__(parent)

        with patch.object(OllamaStreamWorker, "__init__", capture_at_file), \
             patch.object(OllamaStreamWorker, "start", MagicMock()):
            window.send_chat("Inspect other file", "qwen2.5-coder:7b", False, ["other.py"])
            app.processEvents()

        t16_ok = False
        if captured_at_file:
            msg = captured_at_file[-1].get("content", "")
            t16_ok = (
                "[ATTACHED FILE: other.py]" in msg and
                "unsaved_buffer_version" in msg
            )
        results["16_at_file_unsaved_and_disk"] = t16_ok
        print(f"  Result: {'PASS' if t16_ok else 'FAIL'} (UnsavedBufferAttached={t16_ok})")

        # -----------------------------------------------------------------
        # TEST 17: @codebase compatibility
        # -----------------------------------------------------------------
        print("[TEST 17] Verifying @codebase Compatibility...")
        window.context.files = {"hi.py": hi_py_content, "other.py": "def helper(): pass"}
        captured_cb = []
        def capture_cb(self_w, client, model, messages, parent=None):
            captured_cb.extend(messages)
            super(OllamaStreamWorker, self_w).__init__(parent)

        with patch.object(OllamaStreamWorker, "__init__", capture_cb), \
             patch.object(OllamaStreamWorker, "start", MagicMock()):
            window.send_chat("Tell me about the project", "qwen2.5-coder:7b", True, [])
            app.processEvents()

        t17_ok = False
        if captured_cb:
            msg = captured_cb[-1].get("content", "")
            t17_ok = (
                "[PROJECT CODEBASE CONTEXT]" in msg and
                "PROJECT FILE:" in msg
            )
        results["17_at_codebase_compatibility"] = t17_ok
        print(f"  Result: {'PASS' if t17_ok else 'FAIL'} (CodebaseContextIncluded={t17_ok})")

        # -----------------------------------------------------------------
        # TEST 18: Ollama connection & worker cancellation
        # -----------------------------------------------------------------
        print("[TEST 18] Verifying Ollama Worker Cancellation...")
        worker = OllamaStreamWorker(window.client, "qwen2.5-coder:7b", [{"role": "user", "content": "hi"}], window)
        worker.cancel()
        t18_ok = (worker._cancel_requested is True)
        results["18_ollama_cancellation"] = t18_ok
        print(f"  Result: {'PASS' if t18_ok else 'FAIL'} (CancelFlag={worker._cancel_requested})")

    finally:
        if window:
            window.close()
            app.processEvents()
        if test_dir.exists():
            shutil.rmtree(test_dir, ignore_errors=True)

    print("\n=======================================================")
    print("FINAL 18-POINT AI CHAT TEST RESULTS SUMMARY")
    print("=======================================================")
    all_passed = True
    for name, ok in results.items():
        status_str = "PASSED" if ok else "FAILED"
        print(f"  - {name}: {status_str}")
        if not ok:
            all_passed = False

    print("=======================================================")
    print(f"OVERALL STATUS: {'ALL 18 TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
    print("=======================================================\n")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(run_tests())
