import sys
from pathlib import Path
from PIL import Image, ImageDraw
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

src = Path("C:/Users/nithi/.gemini/antigravity/brain/ef9cfd8a-6a2f-4b33-9252-cf8568c8511f/.user_uploaded/media_1793810464420_4348c95f.jpg")
img = Image.open(src)
crop_box = (214, 43, 810, 639)
cropped = img.crop(crop_box)
w, h = cropped.size

# Supersampled antialiased mask
scale = 4
mask_hi = Image.new("L", (w * scale, h * scale), 0)
draw = ImageDraw.Draw(mask_hi)
r_hi = 120 * scale
draw.rounded_rectangle([0, 0, w * scale - 1, h * scale - 1], radius=r_hi, fill=255)
mask = mask_hi.resize((w, h), Image.Resampling.LANCZOS)

rgba = cropped.convert("RGBA")
rgba.putalpha(mask)

test_ico = Path("E:/OpenArise_IDE/OpenArise_IDE/test_win32.ico")
sizes = [(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48), (64, 64), (128, 128), (256, 256)]
rgba.save(test_ico, format="ICO", sizes=sizes)

app = QApplication.instance() or QApplication(sys.argv)
qicon = QIcon(str(test_ico))
avail_sizes = [(sz.width(), sz.height()) for sz in qicon.availableSizes()]
print("PyQt6 QIcon available sizes:", avail_sizes)

# Win32 LoadImageW test
import ctypes
user32 = ctypes.windll.user32
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010
LR_DEFAULTSIZE = 0x0040

hicon_sm = user32.LoadImageW(None, str(test_ico), IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
hicon_lg = user32.LoadImageW(None, str(test_ico), IMAGE_ICON, 32, 32, LR_LOADFROMFILE)
hicon_def = user32.LoadImageW(None, str(test_ico), IMAGE_ICON, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE)

print(f"Win32 LoadImageW: 16x16={bool(hicon_sm)}, 32x32={bool(hicon_lg)}, default={bool(hicon_def)}")

if hicon_sm: user32.DestroyIcon(hicon_sm)
if hicon_lg: user32.DestroyIcon(hicon_lg)
if hicon_def: user32.DestroyIcon(hicon_def)

if test_ico.exists():
    test_ico.unlink()
