"""
Theme definitions and stylesheets for OpenArise IDE.
Provides OpenArise Dark (default), Dracula, Monokai, Nord, and Light.
"""

THEMES = {
    "OpenArise Dark": """
QWidget { background: #17191f; color: #e6e8ef; }
QMainWindow, QDialog, QLabel, QPushButton, QMenu, QMenuBar, QStatusBar, QTabBar, QDockWidget, QToolBar { font-family: Segoe UI, sans-serif; font-size: 10pt; }
QMainWindow, QDialog { background: #17191f; }
QMenuBar, QMenu { background: #20232b; color: #e6e8ef; }
QMenu::item:selected { background: #343a49; }
QToolBar { background: #20232b; border: 0; spacing: 6px; }
QPushButton { background: #303747; border: 1px solid #424b5d; border-radius: 5px; padding: 5px 10px; color: #e6e8ef; }
QPushButton:hover { background: #3d4960; }
QPushButton:pressed { background: #52627d; }
QLineEdit, QTextEdit, QComboBox, QTreeView, QListWidget, QSpinBox {
 background: #1e222b; border: 1px solid #343b49; border-radius: 4px; padding: 4px; color: #e6e8ef;
 selection-background-color: #405d89;
}
QTabWidget::pane { border: 1px solid #343b49; }
QTabBar::tab { background: #222631; padding: 8px 14px; border: 1px solid #343b49; color: #a4adbd; }
QTabBar::tab:selected { background: #343d50; color: #ffffff; }
QStatusBar { background: #20232b; color: #9aa4b5; }
QScrollBar:vertical { background: #1e222b; width: 10px; }
QScrollBar::handle:vertical { background: #465064; min-height: 25px; border-radius: 4px; }
QCheckBox { spacing: 6px; color: #e6e8ef; }
QDockWidget { titlebar-close-icon: url(); titlebar-normal-icon: url(); }
QDockWidget::title { background: #20232b; padding: 4px 8px; font-weight: 600; color: #8ab4f8; }
""",

    "Dracula": """
QWidget { background: #282a36; color: #f8f8f2; }
QMainWindow, QDialog, QLabel, QPushButton, QMenu, QMenuBar, QStatusBar, QTabBar, QDockWidget, QToolBar { font-family: Segoe UI, sans-serif; font-size: 10pt; }
QMainWindow, QDialog { background: #282a36; }
QMenuBar, QMenu { background: #21222c; color: #f8f8f2; }
QMenu::item:selected { background: #44475a; }
QToolBar { background: #21222c; border: 0; spacing: 6px; }
QPushButton { background: #44475a; border: 1px solid #6272a4; border-radius: 5px; padding: 5px 10px; color: #f8f8f2; }
QPushButton:hover { background: #6272a4; }
QPushButton:pressed { background: #bd93f9; color: #282a36; }
QLineEdit, QTextEdit, QComboBox, QTreeView, QListWidget, QSpinBox {
 background: #1e1f29; border: 1px solid #44475a; border-radius: 4px; padding: 4px; color: #f8f8f2;
 selection-background-color: #bd93f9; selection-color: #282a36;
}
QTabWidget::pane { border: 1px solid #44475a; }
QTabBar::tab { background: #21222c; padding: 8px 14px; border: 1px solid #44475a; color: #959da5; }
QTabBar::tab:selected { background: #44475a; color: #50fa7b; font-weight: bold; }
QStatusBar { background: #21222c; color: #8be9fd; }
QScrollBar:vertical { background: #1e1f29; width: 10px; }
QScrollBar::handle:vertical { background: #6272a4; min-height: 25px; border-radius: 4px; }
QCheckBox { spacing: 6px; color: #f8f8f2; }
QDockWidget::title { background: #21222c; padding: 4px 8px; font-weight: 600; color: #ff79c6; }
""",

    "Monokai": """
QWidget { background: #272822; color: #f8f8f2; }
QMainWindow, QDialog, QLabel, QPushButton, QMenu, QMenuBar, QStatusBar, QTabBar, QDockWidget, QToolBar { font-family: Segoe UI, sans-serif; font-size: 10pt; }
QMainWindow, QDialog { background: #272822; }
QMenuBar, QMenu { background: #1e1f1c; color: #f8f8f2; }
QMenu::item:selected { background: #3e3d32; }
QToolBar { background: #1e1f1c; border: 0; spacing: 6px; }
QPushButton { background: #3e3d32; border: 1px solid #75715e; border-radius: 5px; padding: 5px 10px; color: #f8f8f2; }
QPushButton:hover { background: #75715e; }
QPushButton:pressed { background: #a6e22e; color: #272822; }
QLineEdit, QTextEdit, QComboBox, QTreeView, QListWidget, QSpinBox {
 background: #1b1c18; border: 1px solid #3e3d32; border-radius: 4px; padding: 4px; color: #f8f8f2;
 selection-background-color: #f92672; selection-color: #ffffff;
}
QTabWidget::pane { border: 1px solid #3e3d32; }
QTabBar::tab { background: #1e1f1c; padding: 8px 14px; border: 1px solid #3e3d32; color: #8f908a; }
QTabBar::tab:selected { background: #3e3d32; color: #e6db74; }
QStatusBar { background: #1e1f1c; color: #66d9ef; }
QScrollBar:vertical { background: #1b1c18; width: 10px; }
QScrollBar::handle:vertical { background: #75715e; min-height: 25px; border-radius: 4px; }
QCheckBox { spacing: 6px; color: #f8f8f2; }
QDockWidget::title { background: #1e1f1c; padding: 4px 8px; font-weight: 600; color: #a6e22e; }
""",

    "Nord": """
QWidget { background: #2e3440; color: #eceff4; }
QMainWindow, QDialog, QLabel, QPushButton, QMenu, QMenuBar, QStatusBar, QTabBar, QDockWidget, QToolBar { font-family: Segoe UI, sans-serif; font-size: 10pt; }
QMainWindow, QDialog { background: #2e3440; }
QMenuBar, QMenu { background: #242933; color: #eceff4; }
QMenu::item:selected { background: #434c5e; }
QToolBar { background: #242933; border: 0; spacing: 6px; }
QPushButton { background: #3b4252; border: 1px solid #4c566a; border-radius: 5px; padding: 5px 10px; color: #eceff4; }
QPushButton:hover { background: #434c5e; }
QPushButton:pressed { background: #88c0d0; color: #2e3440; }
QLineEdit, QTextEdit, QComboBox, QTreeView, QListWidget, QSpinBox {
 background: #242933; border: 1px solid #434c5e; border-radius: 4px; padding: 4px; color: #eceff4;
 selection-background-color: #88c0d0; selection-color: #2e3440;
}
QTabWidget::pane { border: 1px solid #434c5e; }
QTabBar::tab { background: #242933; padding: 8px 14px; border: 1px solid #434c5e; color: #d8dee9; }
QTabBar::tab:selected { background: #434c5e; color: #88c0d0; }
QStatusBar { background: #242933; color: #81a1c1; }
QScrollBar:vertical { background: #242933; width: 10px; }
QScrollBar::handle:vertical { background: #4c566a; min-height: 25px; border-radius: 4px; }
QCheckBox { spacing: 6px; color: #eceff4; }
QDockWidget::title { background: #242933; padding: 4px 8px; font-weight: 600; color: #88c0d0; }
""",

    "Light": """
QWidget { background: #f6f8fa; color: #24292f; }
QMainWindow, QDialog, QLabel, QPushButton, QMenu, QMenuBar, QStatusBar, QTabBar, QDockWidget, QToolBar { font-family: Segoe UI, sans-serif; font-size: 10pt; }
QMainWindow, QDialog { background: #f6f8fa; }
QMenuBar, QMenu { background: #eaedf1; color: #24292f; }
QMenu::item:selected { background: #d0d7de; }
QToolBar { background: #eaedf1; border: 0; spacing: 6px; }
QPushButton { background: #ffffff; border: 1px solid #d0d7de; border-radius: 5px; padding: 5px 10px; color: #24292f; }
QPushButton:hover { background: #f3f4f6; }
QPushButton:pressed { background: #0969da; color: #ffffff; }
QLineEdit, QTextEdit, QComboBox, QTreeView, QListWidget, QSpinBox {
 background: #ffffff; border: 1px solid #d0d7de; border-radius: 4px; padding: 4px; color: #24292f;
 selection-background-color: #0969da; selection-color: #ffffff;
}
QTabWidget::pane { border: 1px solid #d0d7de; }
QTabBar::tab { background: #eaeef2; padding: 8px 14px; border: 1px solid #d0d7de; color: #57606a; }
QTabBar::tab:selected { background: #ffffff; color: #0969da; font-weight: bold; }
QStatusBar { background: #eaedf1; color: #57606a; }
QScrollBar:vertical { background: #f6f8fa; width: 10px; }
QScrollBar::handle:vertical { background: #d0d7de; min-height: 25px; border-radius: 4px; }
QCheckBox { spacing: 6px; color: #24292f; }
QDockWidget::title { background: #eaedf1; padding: 4px 8px; font-weight: 600; color: #0969da; }
"""
}


def get_theme_stylesheet(theme_name: str) -> str:
    return THEMES.get(theme_name, THEMES["OpenArise Dark"])
