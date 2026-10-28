"""Buduje assets/SnapPMa.ico z ikony rysowanej w kodzie (snappma/icons.py). Wymaga Pillow (tylko do budowy)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from PySide6.QtGui import QGuiApplication

from snappma.icons import app_image

app = QGuiApplication([])
out = Path(__file__).resolve().parent / "assets"
out.mkdir(exist_ok=True)
png = out / "SnapPMa.png"
app_image(256).save(str(png))
from PIL import Image

Image.open(png).save(out / "SnapPMa.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("written", out / "SnapPMa.ico")
