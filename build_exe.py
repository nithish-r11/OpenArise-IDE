import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def main():
    ico_path = ROOT / "assets" / "branding" / "openarise.ico"
    branding_dir = ROOT / "assets" / "branding"
    extensions_dir = ROOT / "assets" / "extensions"

    command = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", "OpenAriseIDE",
        "--icon", str(ico_path),
        "--add-data", f"{branding_dir};assets/branding",
        "--add-data", f"{extensions_dir};assets/extensions",
        "--collect-all", "PyQt6",
        "--collect-all", "markdown",
        "--collect-all", "pygments",
        str(ROOT / "main.py"),
    ]
    print(f"Running PyInstaller: {' '.join(command)}")
    subprocess.run(command, cwd=ROOT, check=True)
    print(f"Build complete: {ROOT / 'dist' / 'OpenAriseIDE.exe'}")

if __name__ == "__main__":
    main()
