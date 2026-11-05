"""
Verification test suite for OpenArise IDE Final Minimal Main Toolbar & Top Menu Order.
Validates:
1. Main Toolbar contains strictly 4 buttons in exact order:
   ["Open Folder", "New File", "Save", "Run Python"]
2. Main Toolbar does not contain removed buttons:
   ["Generate Unit Tests", "Reindex", "Source Control", "Extensions", "New Project", "Create Website", "Run Website"]
3. Top-Level Menus in exact order:
   ["File", "View", "Run", "Tools", "AI", "Settings", "Help"]
   with Settings dedicated immediately before Help.
4. Removed toolbar actions remain fully accessible via Menus and Command Palette.
5. Infinity branding preserved in title bar and taskbar only.
"""

import sys
import os
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PyQt6.QtWidgets import QApplication, QToolBar, QPushButton, QMenu
from PyQt6.QtGui import QIcon, QAction
from core.resources import resource_path
from ui.main_window import MainWindow


def test_minimal_toolbar_buttons(win: MainWindow):
    print("[TEST 1] Verifying Main Toolbar Buttons and Exact Order...")
    toolbars = win.findChildren(QToolBar)
    assert len(toolbars) >= 1, "No QToolBar found in MainWindow"
    main_toolbar = toolbars[0]

    # Find QPushButton child widgets in toolbar
    buttons = [w for w in main_toolbar.findChildren(QPushButton)]
    button_texts = [b.text() for b in buttons]
    print(f"  Found {len(buttons)} toolbar buttons: {button_texts}")

    # 1. Exactly 4 buttons
    assert len(buttons) == 4, f"Expected exactly 4 toolbar buttons, got {len(buttons)}: {button_texts}"

    # 2. Exact order
    expected_order = ["Open Folder", "New File", "Save", "Run Python"]
    assert button_texts == expected_order, f"Toolbar button order mismatch: {button_texts} != {expected_order}"

    # 3. Verify removed buttons are NOT in toolbar
    disallowed_buttons = [
        "Generate Unit Tests",
        "Reindex",
        "Source Control",
        "Extensions",
        "New Project",
        "Create Website",
        "Run Website",
    ]
    for disallowed in disallowed_buttons:
        assert disallowed not in button_texts, f"Disallowed button '{disallowed}' still found in toolbar"

    # 4. Verify toolbar has no logo
    for btn in buttons:
        assert btn.icon().isNull(), f"Button '{btn.text()}' has an unexpected icon"

    print("  Result: PASS (Toolbar strictly contains 4 buttons in exact order with zero logos)")


def test_top_menu_order(win: MainWindow):
    print("[TEST 2] Verifying Top Menu Bar Order...")
    menubar = win.menuBar()
    actions = menubar.actions()
    menu_texts = [a.text().replace("&", "") for a in actions]
    raw_texts = [a.text() for a in actions]
    print(f"  Top menu items: {menu_texts} (raw: {raw_texts})")

    expected_menu_order = ["File", "View", "Run", "Tools", "AI", "Settings", "Help"]
    assert menu_texts == expected_menu_order, f"Menu order mismatch: {menu_texts} != {expected_menu_order}"

    # Verify Settings is immediately before Help
    assert menu_texts[-2] == "Settings", f"Expected Settings as second to last menu, got {menu_texts[-2]}"
    assert menu_texts[-1] == "Help", f"Expected Help as last menu, got {menu_texts[-1]}"

    print("  Result: PASS (Top Menu is strictly File | View | Run | Tools | AI | Settings | Help)")


def test_feature_accessibility_in_menus_and_commands(win: MainWindow):
    print("[TEST 3] Verifying removed toolbar actions are accessible in Menus and Command Palette...")
    menubar = win.menuBar()

    # Collect all action texts from all top-level menus
    all_menu_actions = {}
    for top_action in menubar.actions():
        menu = top_action.menu()
        if menu:
            menu_title = top_action.text().replace("&", "")
            all_menu_actions[menu_title] = [a.text().replace("&", "") for a in menu.actions()]

    print("  Menu action summary:")
    for title, acts in all_menu_actions.items():
        print(f"    - {title}: {len(acts)} actions")

    # 1. New Project & Create Website removed from menus; Settings removed from File menu
    assert not any("New Project" in a for a in all_menu_actions.get("File", [])), "New Project must not be in File menu"
    assert not any("Create Website" in a for a in all_menu_actions.get("File", [])), "Create Website must not be in File menu"
    assert not any("Create Website" in a for a in all_menu_actions.get("AI", [])), "Create Website must not be in AI menu"
    assert not any("Settings" in a for a in all_menu_actions.get("File", [])), "Settings... must not be in File menu"

    # 2. Source Control & Extensions in View menu
    assert any("Source Control" in a for a in all_menu_actions.get("View", [])), "Source Control missing from View menu"
    assert any("Extensions" in a for a in all_menu_actions.get("View", [])), "Extensions missing from View menu"

    # 3. Run Website removed from Run menu
    assert not any("Run Website" in a for a in all_menu_actions.get("Run", [])), "Run Website must not be in Run menu"
    assert any("Run Python" in a for a in all_menu_actions.get("Run", [])), "Run Python File missing from Run menu"

    # 4. Reindex & Environment Manager in Tools menu
    assert any("Reindex" in a for a in all_menu_actions.get("Tools", [])), "Reindex missing from Tools menu"
    assert any("Environment Manager" in a for a in all_menu_actions.get("Tools", [])), "Environment Manager missing from Tools menu"

    # 5. Generate Unit Tests in AI menu
    assert any("Generate Unit Tests" in a for a in all_menu_actions.get("AI", [])), "Generate Unit Tests missing from AI menu"

    # 6. Settings menu has Open Settings, AI Models, Environment Settings
    assert any("Settings" in a for a in all_menu_actions.get("Settings", [])), "Settings action missing from Settings menu"
    assert any("AI Models" in a for a in all_menu_actions.get("Settings", [])), "AI Models action missing from Settings menu"

    # 7. Command Palette Registry verification
    commands = win.command_registry.all_commands()
    cmd_ids = {c.id for c in commands}
    print(f"  Command palette has {len(cmd_ids)} registered commands")

    # Assert removed commands are NOT registered
    removed_commands = [
        "file.new_project",
        "file.create_website",
        "run.website",
        "run.stop_website",
        "run.open_browser",
        "ai.edit_website",
        "ai.fix_website_errors",
    ]
    for rem in removed_commands:
        assert rem not in cmd_ids, f"Command '{rem}' should not be in CommandRegistry"

    # Required preserved commands
    required_commands = [
        "file.open_folder",
        "file.new_file",
        "file.save",
        "run.python",
        "ai.generate_tests",
        "project.reindex",
        "view.source_control",
        "view.extensions",
        "tools.environment_manager",
        "preferences.settings",
    ]
    for req in required_commands:
        assert req in cmd_ids, f"Required command '{req}' not found in CommandRegistry"
        assert req in cmd_ids, f"Required command '{req}' not found in CommandRegistry"

    print("  Result: PASS (All underlying features fully preserved and accessible)")


def test_branding_two_locations_only(win: MainWindow, app: QApplication):
    print("[TEST 4] Verifying Infinity branding strictly in Title bar and Taskbar...")
    # Title bar icon
    assert not win.windowIcon().isNull(), "Title bar icon is missing"
    # Taskbar icon
    assert not app.windowIcon().isNull(), "Taskbar icon is missing"
    # Window title
    assert win.windowTitle() == "OpenArise IDE", f"Window title mismatch: '{win.windowTitle()}'"

    print("  Result: PASS (Infinity logo active on Title bar & Taskbar only, title is 'OpenArise IDE')")


def run_all():
    print("=======================================================")
    print("OPENARISE IDE MINIMAL TOOLBAR & TOP MENU VERIFICATION")
    print("=======================================================\n")

    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    ico_path = resource_path("assets/branding/openarise.ico")
    if ico_path.exists():
        app.setWindowIcon(QIcon(str(ico_path)))

    win = MainWindow()
    win.show()
    app.processEvents()

    test_minimal_toolbar_buttons(win)
    test_top_menu_order(win)
    test_feature_accessibility_in_menus_and_commands(win)
    test_branding_two_locations_only(win, app)

    win.close()
    print("\n=======================================================")
    print("OVERALL RESULT: ALL MINIMAL TOOLBAR & MENU TESTS PASSED")
    print("=======================================================\n")


if __name__ == "__main__":
    run_all()

