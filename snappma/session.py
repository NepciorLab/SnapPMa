"""Jedno przechwytywanie: zrzuty wszystkich monitorow, nakladki, wynik."""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QCursor, QGuiApplication

from .annotations import ToolState
from .foreground import bring_to_front
from .overlay import CaptureOverlay


class CaptureSession(QObject):
    done = Signal(object)           # QImage albo None
    saved = Signal(str)             # zrzut zapisano do pliku JPG

    def __init__(self, state: ToolState, parent=None):
        super().__init__(parent)
        self.state = state
        self.overlays: list[CaptureOverlay] = []

    @property
    def active(self) -> bool:
        return bool(self.overlays)

    def start(self) -> None:
        if self.active:
            return
        # najpierw zrzuty wszystkich ekranow, dopiero potem nakladki, zeby nie trafily na zrzut
        shots = []
        for screen in QGuiApplication.screens():
            image = screen.grabWindow(0).toImage()
            image.setDevicePixelRatio(1.0)
            shots.append((screen, image))
        for screen, image in shots:
            ov = CaptureOverlay(screen, image, self.state)
            ov.finished.connect(self._finish)
            ov.saved.connect(self._saved)
            self.overlays.append(ov)
            ov.show_on_screen()
        under = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        target = next((o for o in self.overlays if o.screen_obj is under), self.overlays[0])
        bring_to_front(target)
        target.setFocus()

    def cancel(self) -> None:
        self._finish(None)

    def _saved(self, path: str) -> None:
        if not self.overlays:
            return
        overlays, self.overlays = self.overlays, []
        for ov in overlays:
            ov.close()
        self.saved.emit(path)

    def _finish(self, image) -> None:
        if not self.overlays:
            return
        overlays, self.overlays = self.overlays, []
        for ov in overlays:
            ov.close()
        self.done.emit(image)
