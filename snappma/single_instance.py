"""Jedna instancja programu (nazwany mutex)."""
from __future__ import annotations

import sys
import time

MUTEX_NAME = "Local\\SnapPMa_single_instance"
ERROR_ALREADY_EXISTS = 183
_handle = None


def acquire(wait_seconds: float = 0.0, name: str = MUTEX_NAME) -> bool:
    """True, gdy to jedyna instancja. Po restarcie (aktualizacja) czekamy chwile, az zamknie sie poprzednia."""
    global _handle
    if sys.platform != "win32":
        return True
    import ctypes
    from ctypes import wintypes
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    deadline = time.monotonic() + wait_seconds
    while True:
        handle = kernel32.CreateMutexW(None, False, name)
        if ctypes.get_last_error() != ERROR_ALREADY_EXISTS:
            _handle = handle
            return True
        kernel32.CloseHandle(handle)
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.2)
