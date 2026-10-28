"""Przechwytywanie klawisza PrintScreen: haczyk klawiatury (WH_KEYBOARD_LL) w osobnym watku.

Haczyk polyka klawisz, wiec Windows 11 nie uruchamia przy nim Narzedzia Wycinanie. Kombinacje z Ctrl, Alt albo Win
(np. Win+PrintScreen, Alt+PrintScreen) przechodza do systemu bez zmian.
"""
from __future__ import annotations

import sys
import threading

from PySide6.QtCore import QObject, Signal

VK_SNAPSHOT = 0x2C
VK_CONTROL, VK_MENU, VK_LWIN, VK_RWIN = 0x11, 0x12, 0x5B, 0x5C
WH_KEYBOARD_LL = 13
WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP = 0x100, 0x101, 0x104, 0x105
LLKHF_INJECTED = 0x10


class PrintScreenFilter:
    """Czysta logika decyzji (bez Windows API), zeby dalo sie ja testowac."""

    def __init__(self):
        self._down = False          # nasz PrintScreen jest wcisniety (polkniety)

    def handle(self, message: int, flags: int, ctrl: bool, alt: bool, win: bool) -> tuple[bool, bool]:
        """Zwraca (polknac, uruchomic zrzut)."""
        if flags & LLKHF_INJECTED:
            return False, False
        if message in (WM_KEYDOWN, WM_SYSKEYDOWN):
            if ctrl or alt or win:
                return False, False
            first = not self._down
            self._down = True
            return True, first      # autopowtarzanie klawisza jest polykane, ale zrzut robimy raz
        if message in (WM_KEYUP, WM_SYSKEYUP):
            if self._down:
                self._down = False
                return True, False
        return False, False


class PrintScreenHook(QObject):
    pressed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._filter = PrintScreenFilter()
        self._thread: threading.Thread | None = None
        self._thread_id = 0
        self._hook = None
        self._proc = None
        self._ready = threading.Event()
        self.installed = False

    def start(self) -> bool:
        if sys.platform != "win32" or self._thread:
            return self.installed
        self._thread = threading.Thread(target=self._run, name="SnapPMaKeyboardHook", daemon=True)
        self._thread.start()
        self._ready.wait(3.0)
        return self.installed

    def stop(self) -> None:
        if self._thread and self._thread_id:
            import ctypes
            ctypes.WinDLL("user32").PostThreadMessageW(self._thread_id, 0x0012, 0, 0)    # WM_QUIT
            self._thread.join(2.0)
        self._thread = None
        self.installed = False

    def _run(self) -> None:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        lresult = ctypes.c_ssize_t
        hookproc = ctypes.WINFUNCTYPE(lresult, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

        class KBDLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD), ("flags", wintypes.DWORD),
                        ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

        user32.SetWindowsHookExW.argtypes = [ctypes.c_int, hookproc, wintypes.HINSTANCE, wintypes.DWORD]
        user32.SetWindowsHookExW.restype = wintypes.HHOOK
        user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
        user32.CallNextHookEx.restype = lresult
        user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
        user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
        user32.GetAsyncKeyState.restype = ctypes.c_short
        user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
        kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        kernel32.GetModuleHandleW.restype = wintypes.HMODULE

        def down(vk: int) -> bool:
            return bool(user32.GetAsyncKeyState(vk) & 0x8000)

        def callback(code, wparam, lparam):
            if code == 0:       # HC_ACTION
                try:
                    kb = ctypes.cast(lparam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                    if kb.vkCode == VK_SNAPSHOT:
                        swallow, fire = self._filter.handle(
                            int(wparam), int(kb.flags), down(VK_CONTROL), down(VK_MENU), down(VK_LWIN) or down(VK_RWIN))
                        if fire:
                            self.pressed.emit()
                        if swallow:
                            return 1
                except Exception:  # noqa: BLE001  - wyjatek w haczyku nie moze zablokowac klawiatury
                    pass
            return user32.CallNextHookEx(None, code, wparam, lparam)

        self._thread_id = kernel32.GetCurrentThreadId()
        self._proc = hookproc(callback)      # referencja, zeby funkcja nie zostala usunieta
        self._hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._proc, kernel32.GetModuleHandleW(None), 0)
        self.installed = bool(self._hook)
        self._ready.set()
        if not self._hook:
            return
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        user32.UnhookWindowsHookEx(self._hook)
        self._hook = None
