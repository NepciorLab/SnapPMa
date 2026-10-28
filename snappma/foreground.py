"""Wysuwanie okna na pierwszy plan (Windows)."""
from __future__ import annotations

import sys


def bring_to_front(window) -> None:
    """Program dzialajacy w tle (obszar powiadomien) nie ma prawa do pierwszego planu, wiec nakladka nie dostawalaby
    klawiatury (Esc, Ctrl+C): dolaczamy sie do watku okna pierwszoplanowego i dopiero wtedy ustawiamy okno."""
    window.raise_()
    window.activateWindow()
    if sys.platform != "win32":
        return
    try:
        import ctypes
        user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
        hwnd = int(window.winId())
        fg = user32.GetForegroundWindow()
        fg_thread = user32.GetWindowThreadProcessId(fg, None) if fg else 0
        me = kernel32.GetCurrentThreadId()
        attached = bool(fg_thread and fg_thread != me and user32.AttachThreadInput(me, fg_thread, True))
        try:
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
            user32.SetFocus(hwnd)
        finally:
            if attached:
                user32.AttachThreadInput(me, fg_thread, False)
    except Exception:  # noqa: BLE001
        pass
