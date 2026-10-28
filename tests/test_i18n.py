import re
from pathlib import Path

from snappma import i18n, translations

ROOT = Path(__file__).resolve().parent.parent
PATTERN = re.compile(r"""\btr\((?:"((?:[^"\\]|\\.)*)"|'((?:[^'\\]|\\.)*)')\)""")


def keys():
    found = set()
    for path in [*ROOT.joinpath("snappma").glob("*.py"), ROOT / "main.py"]:
        if path.name in ("i18n.py", "translations.py"):
            continue
        for m in PATTERN.finditer(path.read_text(encoding="utf-8")):
            found.add(m.group(1) or m.group(2))
    return found


def test_every_ui_text_is_translated():
    found = keys()
    assert len(found) > 20
    assert not [k for k in found if k not in translations.PL], "missing PL"
    assert not [k for k in found if k not in translations.DE], "missing DE"


def test_no_unused_translations():
    found = keys()
    assert set(translations.PL) <= found and set(translations.DE) <= found


def test_language_switch():
    i18n.set_language("pl")
    assert i18n.tr("Rectangle") == "Prostokąt"
    i18n.set_language("de")
    assert i18n.tr("Rectangle") == "Rechteck"
    i18n.set_language("en")
    assert i18n.tr("Rectangle") == "Rectangle"
