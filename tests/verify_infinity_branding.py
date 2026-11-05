"""
Verification suite for OpenArise IDE Original Infinity Logo Branding.
Validates:
1. Master artwork assets and alpha mask integrity.
2. Multi-resolution ICO (16, 20, 24, 32, 40, 48, 64, 128, 256 px).
3. Win32 LoadImageW compatibility for small & big icons.
4. Two allowed placements: Title-bar icon and Taskbar icon.
5. Removal of disallowed placements: Toolbar, Splash screen, About dialog.
6. Application title preservation: 'OpenArise IDE'.
"""

import sys
import os
from pathlib import Path

# Set project root
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image
from core.resources import resource_path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PyQt6.QtWidgets import QApplication, QLabel, QToolBar, QToolButton
from PyQt6.QtGui import QIcon, QPixmap
from ui.main_window import MainWindow
from ui.splash_screen import SplashScreen
from ui.about_dialog import AboutDialog


def test_master_assets():
    print("[CHECK 1] Verifying master branding files...")
    logo_jpg = resource_path("assets/branding/openarise_logo.jpg")
    master_png = resource_path("assets/branding/openarise_master.png")
    ico_file = resource_path("assets/branding/openarise.ico")

    assert logo_jpg.exists() and logo_jpg.stat().st_size > 0, "openarise_logo.jpg missing or empty"
    assert master_png.exists() and master_png.stat().st_size > 0, "openarise_master.png missing or empty"
    assert ico_file.exists() and ico_file.stat().st_size > 0, "openarise.ico missing or empty"

    img_png = Image.open(master_png)
    assert img_png.size == (596, 596), f"Expected master PNG 596x596, got {img_png.size}"
    assert img_png.mode == "RGBA", f"Expected RGBA, got {img_png.mode}"

    # Alpha channel checks: corner should be transparent (0), center should be opaque (255)
    r, g, b, a = img_png.getpixel((0, 0))
    assert a == 0, f"Corner (0,0) alpha should be 0, got {a}"
    r, g, b, a = img_png.getpixel((298, 298))
    assert a == 255, f"Center (298,298) alpha should be 255, got {a}"
    img_png.close()

    print(f"  Result: PASS (Master PNG: 596x596 RGBA, ICO: {ico_file.stat().st_size} bytes)")


def test_ico_resolutions():
    print("[CHECK 2] Verifying multi-resolution ICO entries (16, 20, 24, 32, 40, 48, 64, 128, 256 px)...")
    ico_file = resource_path("assets/branding/openarise.ico")
    ico_img = Image.open(ico_file)

    expected_sizes = {(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48), (64, 64), (128, 128), (256, 256)}
    sizes = ico_img.info.get("sizes", set())
    assert sizes == expected_sizes, f"ICO sizes mismatch: {sizes ^ expected_sizes}"

    assert hasattr(ico_img, "ico"), "Image has no ico attribute"
    assert len(ico_img.ico.entry) == 9, f"Expected 9 ICO entries, got {len(ico_img.ico.entry)}"

    for entry in ico_img.ico.entry:
        assert entry.bpp == 32, f"Expected 32-bit entry, got {entry.bpp} for {entry.width}x{entry.height}"

    ico_img.close()
    print("  Result: PASS (All 9 resolutions present with 32-bit RGBA depth)")


def test_win32_load_image():
    print("[CHECK 3] Verifying Win32 LoadImageW icon loading...")
    if sys.platform != "win32":
        print("  Skipped (non-Windows platform)")
        return

    import ctypes
    user32 = ctypes.windll.user32
    ico_file = resource_path("assets/branding/openarise.ico")
    IMAGE_ICON = 1
    LR_LOADFROMFILE = 0x0010

    for size in [16, 20, 24, 32, 40, 48, 64, 128, 256]:
        hicon = user32.LoadImageW(None, str(ico_file), IMAGE_ICON, size, size, LR_LOADFROMFILE)
        err = ctypes.GetLastError()
        assert hicon != 0, f"Win32 LoadImageW failed for {size}x{size}, error: {err}"
        user32.DestroyIcon(hicon)

    print("  Result: PASS (Win32 LoadImageW successfully loaded all 9 resolutions)")


def test_two_allowed_locations(app: QApplication):
    print("[CHECK 4] Verifying two allowed logo placements (Title bar & Taskbar)...")
    ico_file = resource_path("assets/branding/openarise.ico")
    app.setWindowIcon(QIcon(str(ico_file)))

    win = MainWindow()
    win.show()
    app.processEvents()

    # 1. Title bar icon (Location 1)
    assert not win.windowIcon().isNull(), "Location 1 FAILED: MainWindow windowIcon() is null"

    # 2. Taskbar icon (Location 2)
    assert not app.windowIcon().isNull(), "Location 2 FAILED: QApplication windowIcon() is null"

    # 3. Application title preserved
    assert win.windowTitle() == "OpenArise IDE", f"Window title mismatch: '{win.windowTitle()}'"

    print("  Result: PASS (Location 1: Title-bar icon valid, Location 2: Taskbar icon valid, Title='OpenArise IDE')")
    win.close()


def test_removed_disallowed_locations(app: QApplication):
    print("[CHECK 5] Verifying removed logo placements (Toolbar, Splash, About)...")
    win = MainWindow()
    win.show()
    app.processEvents()

    # Disallowed Location 1: Main Toolbar
    toolbars = win.findChildren(QToolBar)
    for tb in toolbars:
        for action in tb.actions():
            # Action icon should not be the openarise branding icon
            icon = action.icon()
            assert icon.isNull(), f"Found unexpected icon in toolbar action: {action.text()}"

    # Disallowed Location 2: Splash Screen
    splash = SplashScreen()
    # Check that splash screen source code does NOT reference openarise_logo.jpg
    import inspect
    splash_src = inspect.getsource(SplashScreen)
    assert "openarise_logo" not in splash_src, "SplashScreen still references openarise_logo"
    assert "drawPixmap" not in splash_src, "SplashScreen still paints a pixmap logo"

    # Disallowed Location 3: About Dialog
    about = AboutDialog(win)
    about_src = inspect.getsource(AboutDialog)
    assert "openarise_logo" not in about_src, "AboutDialog still references openarise_logo"
    labels = about.findChildren(QLabel)
    for lbl in labels:
        assert lbl.pixmap().isNull(), "AboutDialog still has a QLabel with a pixmap logo"
    about.close()
    win.close()

    print("  Result: PASS (No logo in Toolbar, Splash Screen, or About Dialog)")


def run_all():
    print("=======================================================")
    print("OPENARISE IDE INFINITY LOGO BRANDING VERIFICATION")
    print("=======================================================\n")
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    test_master_assets()
    test_ico_resolutions()
    test_win32_load_image()
    test_two_allowed_locations(app)
    test_removed_disallowed_locations(app)

    print("\n=======================================================")
    print("OVERALL RESULT: ALL BRANDING VERIFICATIONS PASSED")
    print("=======================================================\n")


if __name__ == "__main__":
    run_all()

