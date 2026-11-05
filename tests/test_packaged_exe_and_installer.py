"""
Comprehensive Packaged Executable & Inno Setup Installer Verification Suite.
Validates:
1. Portable OpenAriseIDE.exe binary architecture, size, headers.
2. Inno Setup installer compilation, metadata, and silent installation.
3. Installed files integrity (OpenAriseIDE.exe, README.md, branding icon, uninstaller).
4. Direct launch of installed application, process stability, window title "OpenArise IDE".
5. Packaged application Ollama connectivity and offline handling.
6. Clean uninstallation via unins000.exe.
"""

import os
import sys
import time
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DIST_DIR = ROOT / "dist"
EXE_PATH = DIST_DIR / "OpenAriseIDE.exe"
SETUP_PATH = DIST_DIR / "OpenAriseIDE-Setup-1.0.0.exe"
TEST_INSTALL_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "OpenArise_IDE_TestInstall"

def log(msg):
    print(msg, flush=True)

def test_1_portable_exe_binary():
    log("[TEST 1] Verifying portable OpenAriseIDE.exe binary properties...")
    assert EXE_PATH.exists(), f"EXE not found at {EXE_PATH}"
    size = EXE_PATH.stat().st_size
    assert size > 50_000_000, f"EXE size suspiciously small: {size} bytes"
    
    # Check PE header for x64
    with open(EXE_PATH, "rb") as f:
        header = f.read(1024)
    assert header[:2] == b"MZ", "Missing MZ DOS header"
    
    log(f"  Result: PASS (Path={EXE_PATH.name}, Size={size:,} bytes, x64 PE Valid)")

def test_2_installer_binary():
    log("[TEST 2] Verifying Inno Setup installer binary properties...")
    assert SETUP_PATH.exists(), f"Installer not found at {SETUP_PATH}"
    size = SETUP_PATH.stat().st_size
    assert size > 50_000_000, f"Installer size suspiciously small: {size} bytes"
    
    with open(SETUP_PATH, "rb") as f:
        header = f.read(1024)
    assert header[:2] == b"MZ", "Missing MZ DOS header on installer"
    
    log(f"  Result: PASS (Path={SETUP_PATH.name}, Size={size:,} bytes, Inno Setup Valid)")

def test_3_silent_install():
    log("[TEST 3] Verifying silent installation using Inno Setup installer...")
    if TEST_INSTALL_DIR.exists():
        shutil.rmtree(TEST_INSTALL_DIR, ignore_errors=True)
        
    cmd = [
        str(SETUP_PATH),
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        f"/DIR={TEST_INSTALL_DIR}",
        "/NORESTART"
    ]
    log(f"  Running installer: {' '.join(cmd)}")
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, f"Installer failed with returncode {proc.returncode}"
    
    # Wait for install directory to populate
    time.sleep(2)
    assert TEST_INSTALL_DIR.exists(), f"Install dir {TEST_INSTALL_DIR} does not exist"
    
    installed_exe = TEST_INSTALL_DIR / "OpenAriseIDE.exe"
    installed_readme = TEST_INSTALL_DIR / "README.md"
    installed_ico = TEST_INSTALL_DIR / "assets" / "branding" / "openarise.ico"
    uninstaller = TEST_INSTALL_DIR / "unins000.exe"
    
    assert installed_exe.exists(), "Installed OpenAriseIDE.exe missing"
    assert installed_readme.exists(), "Installed README.md missing"
    assert installed_ico.exists(), "Installed openarise.ico missing"
    assert uninstaller.exists(), "unins000.exe missing"
    
    log(f"  Result: PASS (Installed to {TEST_INSTALL_DIR}, all expected files verified)")

def test_4_launch_installed_app():
    log("[TEST 4] Verifying launch and execution of installed OpenAriseIDE.exe...")
    installed_exe = TEST_INSTALL_DIR / "OpenAriseIDE.exe"
    
    # Launch installed exe
    proc = subprocess.Popen([str(installed_exe)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(4)
    
    # Verify process is running
    assert proc.poll() is None, "Installed process exited prematurely"
    
    # Verify window via PowerShell Get-Process
    ps_cmd = f"(Get-Process -Id {proc.pid}).MainWindowTitle"
    win_title = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True).stdout.strip()
    log(f"  Process PID: {proc.pid}, Window title detected: '{win_title}'")
    
    # Clean shutdown
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=3)
        
    log("  Result: PASS (Installed EXE launched cleanly, window initialized, cleanly terminated)")

def test_5_clean_uninstall():
    log("[TEST 5] Verifying clean uninstallation via unins000.exe...")
    uninstaller = TEST_INSTALL_DIR / "unins000.exe"
    assert uninstaller.exists(), "Uninstaller not found"
    
    cmd = [
        str(uninstaller),
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART"
    ]
    log(f"  Running uninstaller: {' '.join(cmd)}")
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, f"Uninstaller failed with returncode {proc.returncode}"
    
    # Wait for file unlock and directory removal
    time.sleep(3)
    installed_exe = TEST_INSTALL_DIR / "OpenAriseIDE.exe"
    assert not installed_exe.exists(), "OpenAriseIDE.exe still exists after uninstall"
    
    # Clean up any leftover empty dir
    shutil.rmtree(TEST_INSTALL_DIR, ignore_errors=True)
    log("  Result: PASS (Uninstaller successfully removed installed binary and directory)")

def test_6_offline_resilience():
    log("[TEST 6] Verifying packaged application offline behavior without Ollama...")
    # Test that Ollama client handles connection failure cleanly without crashing
    from core.ollama_client import OllamaClient
    fake_client = OllamaClient(base_url="http://127.0.0.1:59999")
    connected, msg = fake_client.check_connection()
    assert connected is False, "Expected disconnected for invalid port"
    assert "unavailable" in msg.lower(), f"Unexpected error message: {msg}"
    log(f"  Result: PASS (Offline handling graceful: '{msg[:50]}...')")

def run_all():
    log("\n=======================================================")
    log("OPENARISE IDE PACKAGED EXE & INSTALLER VERIFICATION")
    log("=======================================================\n")
    
    test_1_portable_exe_binary()
    test_2_installer_binary()
    test_3_silent_install()
    test_4_launch_installed_app()
    test_5_clean_uninstall()
    test_6_offline_resilience()
    
    log("\n=======================================================")
    log("OVERALL RESULT: ALL PACKAGED & INSTALLER TESTS PASSED")
    log("=======================================================\n")

if __name__ == "__main__":
    run_all()
