import io
import winreg

from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor

from snappma import autostart, updater
from snappma.annotations import Item, arrow_geometry, constrain_axis, constrain_square, is_degenerate
from snappma.hotkey import LLKHF_INJECTED, WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, PrintScreenFilter
from snappma.settings import Settings


def test_filter_swallows_plain_printscreen_once():
    f = PrintScreenFilter()
    assert f.handle(WM_KEYDOWN, 0, False, False, False) == (True, True)
    assert f.handle(WM_KEYDOWN, 0, False, False, False) == (True, False)       # autopowtarzanie
    assert f.handle(WM_KEYUP, 0, False, False, False) == (True, False)
    assert f.handle(WM_KEYDOWN, 0, False, False, False) == (True, True)        # kolejne wcisniecie


def test_filter_passes_modified_and_injected():
    f = PrintScreenFilter()
    assert f.handle(WM_KEYDOWN, 0, True, False, False) == (False, False)       # Ctrl+PrintScreen
    assert f.handle(WM_SYSKEYDOWN, 0, False, True, False) == (False, False)    # Alt+PrintScreen
    assert f.handle(WM_KEYDOWN, 0, False, False, True) == (False, False)       # Win+PrintScreen
    assert f.handle(WM_KEYUP, 0, False, False, False) == (False, False)        # puszczenie po przepuszczonym
    assert f.handle(WM_KEYDOWN, LLKHF_INJECTED, False, False, False) == (False, False)


def test_constrain():
    assert constrain_axis(QPointF(5, 5), QPointF(50, 12)) == QPointF(50, 5)
    assert constrain_axis(QPointF(5, 5), QPointF(12, 50)) == QPointF(5, 50)
    assert constrain_square(QPointF(0, 0), QPointF(30, -10)) == QPointF(30, -30)


def test_arrow_geometry():
    assert arrow_geometry(QPointF(0, 0), QPointF(0, 0), 4) is None
    shaft_end, head = arrow_geometry(QPointF(0, 0), QPointF(100, 0), 4)
    assert head.at(0) == QPointF(100, 0) and 0 < shaft_end.x() < 100


def test_degenerate():
    c = QColor("red")
    assert is_degenerate(Item("line", c, 3, [QPointF(1, 1), QPointF(1, 1)]))
    assert not is_degenerate(Item("line", c, 3, [QPointF(1, 1), QPointF(2, 1)]))
    assert not is_degenerate(Item("pen", c, 3, [QPointF(1, 1)]))


def test_versions_and_assets():
    assert updater.parse_version("v1.10.0") > updater.parse_version("1.9.9")
    assert updater.parse_version("1.0.0") == updater.parse_version("v1.0.0")
    rel = {"tag_name": "v1.1.0", "assets": [
        {"name": "notes.txt", "browser_download_url": "https://x/notes.txt"},
        {"name": "other.exe", "browser_download_url": "https://x/other.exe"},
        {"name": "SnapPMa.exe", "browser_download_url": "https://x/SnapPMa.exe"},
        {"name": "evil.exe", "browser_download_url": "http://x/evil.exe"}]}
    assert updater.pick_asset(rel)["name"] == "SnapPMa.exe"
    rel["assets"] = [rel["assets"][1], rel["assets"][3]]
    assert updater.pick_asset(rel)["name"] == "other.exe"          # http jest odrzucane
    assert updater.pick_asset({"assets": []}) is None
    assert updater.valid_repo("NepciorLab/SnapPMa") and not updater.valid_repo("a b/c") and not updater.valid_repo("x")


def test_update_job_with_fake_release(qapp, monkeypatch):
    monkeypatch.setattr(updater, "fetch_release", lambda repo, timeout=15: {
        "tag_name": "v9.0.0",
        "assets": [{"name": "SnapPMa.exe", "browser_download_url": "https://x/SnapPMa.exe", "size": 5}]})
    got = []
    sig = updater.UpdateSignals()
    sig.result.connect(lambda *a: got.append(a))
    updater.UpdateJob("a/b", "1.0.0", False, sig).run()
    updater.UpdateJob("a/b", "9.0.0", False, sig).run()
    updater.UpdateJob("bad repo", "1.0.0", False, sig).run()
    assert got[0][:3] == ("newer", "9.0.0", "https://x/SnapPMa.exe")
    assert got[1][0] == "current"
    assert got[2][0] == "error"


def test_download_rejects_non_exe(tmp_path, monkeypatch):
    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    monkeypatch.setattr(updater.urllib.request, "urlopen", lambda req, timeout=0: Resp(b"<html>not an exe"))
    dest = tmp_path / "SnapPMa.exe.new"
    try:
        updater.download("https://x/y.exe", dest)
        raised = False
    except OSError:
        raised = True
    assert raised and not list(tmp_path.iterdir())
    monkeypatch.setattr(updater.urllib.request, "urlopen", lambda req, timeout=0: Resp(b"MZ" + b"\0" * 10))
    updater.download("https://x/y.exe", dest, expected_size=12)
    assert dest.stat().st_size == 12


def test_autostart_roundtrip_in_sandbox_key():
    key = r"Software\SnapPMaTest\Run"
    try:
        assert not autostart.is_enabled(key)
        autostart.set_enabled(True, key)
        assert autostart.is_enabled(key)
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
            value = winreg.QueryValueEx(k, "SnapPMa")[0]
        assert value.endswith("--autostart") and "main.py" in value
        autostart.set_enabled(False, key)
        assert not autostart.is_enabled(key)
        autostart.set_enabled(False, key)                           # wylaczenie nieobecnego wpisu nie psuje
    finally:
        for sub in (key, r"Software\SnapPMaTest"):
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, sub)
            except OSError:
                pass


def test_settings_roundtrip(tmp_path, qapp):
    ini = tmp_path / "t.ini"
    s = Settings(str(ini))
    assert s.get("Program/autostart") is False and s.get("Tools/width") == 4
    s.set("Program/autostart", True)
    s.set("Tools/width", 9)
    s.set("Tools/color", "#112233")
    s2 = Settings(str(ini))
    assert s2.get("Program/autostart") is True and s2.get("Tools/width") == 9 and s2.get("Tools/color") == "#112233"
    text = ini.read_text(encoding="utf-8")
    assert "[Program]" in text and "[Tools]" in text and "[%General]" not in text
