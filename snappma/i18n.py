"""Tlumaczenia: kluczem jest angielski tekst w tr("..."); jezyk wybierany przy starcie programu."""
from __future__ import annotations

from . import translations

LANGUAGES = ("en", "pl", "de")
_lang = "en"


def detect_language() -> str:
    from PySide6.QtCore import QLocale
    code = QLocale.system().name()[:2].lower()
    return code if code in LANGUAGES else "en"


def set_language(code: str) -> None:
    global _lang
    code = (code or "auto").lower()
    _lang = detect_language() if code == "auto" else (code if code in LANGUAGES else "en")


def language() -> str:
    return _lang


def tr(text: str) -> str:
    table = {"pl": translations.PL, "de": translations.DE}.get(_lang)
    return table.get(text, text) if table else text
