import sys
from pathlib import Path

def resource_path(relative_path: str) -> Path:
    """
    Get absolute path to resource, compatible with both local development
    and PyInstaller one-file executable mode (via sys._MEIPASS).
    """
    if hasattr(sys, "_MEIPASS"):
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).resolve().parent.parent
    return (base_path / relative_path).resolve()

