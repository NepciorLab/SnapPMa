"""Sciezki programu (zrodla albo spakowany .exe)."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from .version import APP_NAME

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_dir() -> Path:
    """Katalog programu: obok .exe albo katalog projektu."""
    return Path(sys.executable).parent if is_frozen() else PROJECT_ROOT


def _writable(folder: Path) -> bool:
    try:
        with tempfile.TemporaryFile(dir=folder):
            return True
    except OSError:
        return False


def settings_path() -> Path:
    """SnapPMa.ini obok programu; gdy tam nie wolno zapisywac (np. Program Files), w %APPDATA%."""
    folder = app_dir()
    if _writable(folder):
        return folder / f"{APP_NAME}.ini"
    fallback = Path(os.environ.get("APPDATA", str(Path.home()))) / APP_NAME
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback / f"{APP_NAME}.ini"


def launch_command() -> list[str]:
    """Polecenie uruchamiajace program (do autostartu i restartu po aktualizacji)."""
    if is_frozen():
        return [sys.executable]
    pyw = Path(sys.executable).with_name("pythonw.exe")
    return [str(pyw if pyw.is_file() else Path(sys.executable)), str(PROJECT_ROOT / "main.py")]
