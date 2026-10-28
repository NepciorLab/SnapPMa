"""Ustawienia programu -> SnapPMa.ini (sekcje [Program] i [Tools]; sekcji General nie uzywamy, Qt zmienia ja na [%General])."""
from __future__ import annotations

from PySide6.QtCore import QSettings

from .paths import settings_path
from .version import GITHUB_REPO

DEFAULTS: dict[str, object] = {
    "Program/language": "auto",          # auto | en | pl | de
    "Program/autostart": False,
    "Program/auto_update": False,
    "Program/notify_start": True,        # komunikat w obszarze powiadomien po uruchomieniu programu
    "Program/notify": True,              # komunikat w obszarze powiadomien po skopiowaniu
    "Program/github_repo": GITHUB_REPO,
    "Tools/color": "#E53935",
    "Tools/width": 4,
}


class Settings:
    def __init__(self, path: str | None = None):
        self.path = str(path or settings_path())
        self._q = QSettings(self.path, QSettings.IniFormat)

    def get(self, key: str):
        default = DEFAULTS[key]
        value = self._q.value(key, default)
        if isinstance(default, bool):
            return value if isinstance(value, bool) else str(value).strip().lower() in ("true", "1", "yes")
        if isinstance(default, int):
            try:
                return int(value)
            except (TypeError, ValueError):
                return default
        return str(value)

    def set(self, key: str, value) -> None:
        self._q.setValue(key, value)
        self._q.sync()
