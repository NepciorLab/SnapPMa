"""Uruchamianie razem z Windows: wpis w HKCU\\...\\Run (bez uprawnien administratora)."""
from __future__ import annotations

import subprocess
import sys

from .paths import launch_command
from .version import APP_NAME

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"      # w testach podmieniany na klucz probny


def command() -> str:
    return subprocess.list2cmdline(launch_command() + ["--autostart"])


def is_enabled(key_path: str | None = None) -> bool:
    if sys.platform != "win32":
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path or RUN_KEY) as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except FileNotFoundError:
        return False


def set_enabled(enabled: bool, key_path: str | None = None) -> None:
    """Wlacza albo wylacza autostart; przy wlaczeniu odswieza tez sciezke (program mogl zostac przeniesiony)."""
    if sys.platform != "win32":
        return
    import winreg
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path or RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command())
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
