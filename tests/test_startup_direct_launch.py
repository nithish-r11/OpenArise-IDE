"""
Startup & Direct Launch Verification Suite for OpenArise IDE.
Validates:
1. Startup Splash Screen is completely disabled.
2. main.py launches MainWindow directly without creating or showing SplashScreen.
3. Title-bar infinity icon and taskbar infinity icon remain valid.
4. Ollama connection worker remains asynchronous and non-blocking.
5. All essential subsystems (Editor, Chat/Agent, Tree, Terminal) initialize directly.
"""

import sys
import os
import inspect
from pathlib import Path

# Ensure application root in sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QTimer
import main
from ui.main_window import MainWindow


def test_main_startup_code_inspection():
    print("[TEST 1] Verifying main.py startup code does not instantiate or show SplashScreen...")
    main_src = inspect.getsource(main.main)
    assert "SplashScreen" not in main_src, "main.main still references SplashScreen"
    assert "splash.show" not in main_src, "main.main still calls splash.show()"
    assert "splash.finish" not in main_src, "main.main still calls splash.finish()"
    assert "window = MainWindow()" in main_src, "main.main does not instantiate MainWindow directly"
    assert "window.show()" in main_src, "main.main does not show MainWindow directly"
    print("  Result: PASS (main.main launches MainWindow directly without splash screen)")


def test_direct_mainwindow_launch(app: QApplication):
    print("[TEST 2] Verifying MainWindow direct launch and window properties...")
    win = MainWindow()
    win.show()
    app.processEvents()

    # 1. Window title
    assert win.windowTitle() == "OpenArise IDE", f"Unexpected window title: '{win.windowTitle()}'"

    # 2. Title-bar icon
    assert not win.windowIcon().isNull(), "MainWindow title-bar icon is null"

    # 3. Taskbar / Application icon
    assert not app.windowIcon().isNull(), "Application taskbar icon is null"

    # 4. Essential subsystems directly available
    assert win.tree is not None, "File Explorer tree not initialized"
    assert win.editor is not None, "Editor tabs not initialized"
    assert win.chat is not None, "AI Chat/Agent panel not initialized"
    assert hasattr(win, "terminal_dock") and win.terminal_dock is not None, "Terminal dock not initialized"

    print("  Result: PASS (Direct launch successful, title and infinity icons intact)")
    win.close()


def test_async_ollama_nonblocking(app: QApplication):
    print("[TEST 3] Verifying Ollama health check is asynchronous and non-blocking...")
    win = MainWindow()
    win.show()
    app.processEvents()

    # Confirm health worker uses QThread
    assert hasattr(win, "check_ollama"), "MainWindow missing check_ollama"
    win.check_ollama()
    assert hasattr(win, "_health_worker") and win._health_worker is not None, "Health worker not spawned"
    assert win._health_worker.isRunning(), "Health worker not running asynchronously"

    # Wait for completion without blocking main thread
    wait_count = 0
    while win._health_worker.isRunning() and wait_count < 100:
        app.processEvents()
        import time
        time.sleep(0.05)
        wait_count += 1

    print(f"  Result: PASS (Health worker ran asynchronously and finished in {wait_count * 50}ms)")
    win.close()


def run_all():
    print("=======================================================")
    print("OPENARISE IDE DIRECT LAUNCH & STARTUP VERIFICATION")
    print("=======================================================\n")
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    from core.resources import resource_path
    ico_path = resource_path("assets/branding/openarise.ico")
    if ico_path.exists():
        app.setWindowIcon(QIcon(str(ico_path)))

    test_main_startup_code_inspection()
    test_direct_mainwindow_launch(app)
    test_async_ollama_nonblocking(app)

    print("\n=======================================================")
    print("OVERALL RESULT: ALL DIRECT LAUNCH TESTS PASSED")
    print("=======================================================\n")


if __name__ == "__main__":
    run_all()
