"""Samotest bez okna (QT_QPA_PLATFORM=offscreen): sprawdza rysowanie, skladanie wyniku, ikony i tlumaczenia.

Uzywany przez `SnapPMa.exe --selftest wynik.txt` oraz przez testy. Nie instaluje haczyka klawiatury i nic nie pokazuje.
"""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QPointF, QSize, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage
from PySide6.QtWidgets import QApplication

from . import autostart
from .annotations import ToolState, constrain_axis
from .hotkey import WM_KEYDOWN, WM_KEYUP, PrintScreenFilter
from .icons import app_icon, tool_icon
from .overlay import CaptureOverlay
from .updater import parse_version

W, H = 400, 300


def make_shot() -> QImage:
    img = QImage(W, H, QImage.Format_RGB32)
    img.fill(QColor("#FFFFFF"))
    return img


def drag(ov: CaptureOverlay, a: tuple[float, float], b: tuple[float, float], mods=Qt.NoModifier) -> None:
    ov._press(QPointF(*a), Qt.LeftButton, mods)
    ov._move(QPointF((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), mods, True)
    ov._move(QPointF(*b), mods, True)
    ov._release(QPointF(*b), Qt.LeftButton, mods)


def new_overlay(state: ToolState | None = None) -> tuple[CaptureOverlay, list]:
    ov = CaptureOverlay(QGuiApplication.primaryScreen(), make_shot(), state or ToolState("#E53935", 4))
    ov.setGeometry(0, 0, W, H)
    results: list = []
    ov.finished.connect(results.append)
    return ov, results


def check_selection_and_drawing() -> bool:
    ov, results = new_overlay()
    drag(ov, (50, 40), (250, 190))                                  # zaznaczenie 200x150
    ok = ov.phase == "edit" and ov.sel.width() == 200 and ov.sel.height() == 150
    ov.toolbar.set_tool("line")
    drag(ov, (60, 100), (200, 130), Qt.ShiftModifier)               # Shift: pozioma
    ok = ok and len(ov.items) == 1 and ov.items[0].points[1].y() == ov.items[0].points[0].y()
    ov.toolbar.set_tool("rect")
    drag(ov, (70, 60), (120, 90))
    ov.toolbar.set_tool("pointer")
    drag(ov, (150, 150), (150, 150))
    ok = ok and len(ov.items) == 3
    ov.undo()
    ok = ok and len(ov.items) == 2
    ov.copy_selection()
    img = results[0] if results else None
    return bool(ok and img is not None and (img.width(), img.height()) == (200, 150)
                and QColor(img.pixel(80, 60)).name() == "#e53935" and QColor(img.pixel(80, 100)).name() == "#ffffff")


def check_filter() -> bool:
    f = PrintScreenFilter()
    return (f.handle(WM_KEYDOWN, 0, False, False, False) == (True, True)
            and f.handle(WM_KEYDOWN, 0, False, False, False) == (True, False)
            and f.handle(WM_KEYUP, 0, False, False, False) == (True, False)
            and f.handle(WM_KEYDOWN, 0, False, True, False) == (False, False))


def check_jpeg_save() -> bool:
    import os
    import tempfile

    from .annotations import save_jpeg
    img = make_shot()
    img.fill(QColor("#336699"))
    with tempfile.TemporaryDirectory() as folder:
        path = save_jpeg(img, os.path.join(folder, "t"), 90)         # bez rozszerzenia: dopisuje .jpg
        back = QImage(path)
        return path.endswith(".jpg") and (back.width(), back.height()) == (W, H) and abs(QColor(back.pixel(5, 5)).blue() - 0x99) < 12


CHECKS: list[tuple[str, Callable[[], bool]]] = [
    ("JPEG save (plugin)", check_jpeg_save),
    ("selection, tools, copy", check_selection_and_drawing),
    ("PrintScreen filter", check_filter),
    ("shift constrain", lambda: constrain_axis(QPointF(0, 0), QPointF(10, 3)) == QPointF(10, 0)),
    ("icons", lambda: not tool_icon("arrow").isNull() and not app_icon().isNull()
     and not tool_icon("pen").pixmap(QSize(24, 24)).isNull()),
    ("version parsing", lambda: parse_version("v1.2.10") > parse_version("1.2.9")),
    ("autostart command", lambda: autostart.command().endswith("--autostart")),
]


def run(out_path: str) -> int:
    app = QApplication.instance() or QApplication([])
    lines, failed = [], 0
    for name, fn in CHECKS:
        try:
            ok = bool(fn())
        except Exception as exc:  # noqa: BLE001
            ok, name = False, f"{name} ({exc!r})"
        failed += 0 if ok else 1
        lines.append(f"{'OK  ' if ok else 'FAIL'} {name}")
    lines.append("ALL OK" if not failed else f"{failed} FAILED")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    del app
    return 1 if failed else 0
