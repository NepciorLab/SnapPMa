"""Smoke test calego programu bez haczyka klawiatury i bez dotykania rejestru."""
import pytest
from PySide6.QtGui import QGuiApplication

from snappma import app as app_module
from snappma import session as session_module
from snappma import updater
from snappma.settings import Settings


@pytest.fixture
def snappma(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(app_module.PrintScreenHook, "start", lambda self: True)      # bez prawdziwego haczyka
    monkeypatch.setattr(session_module, "bring_to_front", lambda w: None)           # bez WinAPI na oknach offscreen
    monkeypatch.setattr(app_module, "UPDATE_FIRST_CHECK_MS", 10 ** 9)
    window = app_module.SnapPMaApp(Settings(str(tmp_path / "t.ini")), quiet_start=True)
    yield window
    window.session.cancel()
    window.tray.hide()


def test_capture_copies_to_clipboard(snappma):
    snappma.capture()
    assert snappma.session.active
    ov = snappma.session.overlays[0]
    from snappma.selftest import drag
    drag(ov, (20, 20), (120, 90))
    ov.toolbar.set_tool("arrow")
    drag(ov, (30, 30), (100, 70))
    ov.copy_selection()
    assert not snappma.session.active
    img = QGuiApplication.clipboard().image()
    assert not img.isNull() and img.width() >= 100


def test_second_printscreen_restarts_capture(snappma, qapp):
    snappma.capture()
    first = snappma.session.overlays[0]
    snappma.capture()
    assert not snappma.session.active
    from PySide6.QtTest import QTest
    QTest.qWait(app_module.RECAPTURE_DELAY_MS + 100)
    assert snappma.session.active and snappma.session.overlays[0] is not first


def test_escape_cancels_and_saves_tool_settings(snappma):
    snappma.capture()
    snappma.state.width = 11
    snappma.session.overlays[0].cancel()
    assert not snappma.session.active
    assert snappma.settings.get("Tools/width") == 11


def test_update_results(snappma, monkeypatch):
    shown = []
    monkeypatch.setattr(snappma, "_message", lambda text, warning=False: shown.append(text))
    snappma._manual_check = True
    snappma._on_update_result("current", "1.0.0", "", "")
    snappma._on_update_result("error", "", "", "HTTP 404")
    snappma._on_update_result("newer", "9.9.9", "https://x/SnapPMa.exe", "")
    assert len(shown) == 3 and "404" in shown[1] and "9.9.9" in shown[2]
    snappma._manual_check = False
    snappma._on_update_result("current", "1.0.0", "", "")
    assert len(shown) == 3                                   # automatyczne sprawdzenie nic nie mowi, gdy brak nowej wersji


def test_ready_update_waits_while_capturing(snappma, monkeypatch):
    called = []
    monkeypatch.setattr(updater, "install_update", lambda path: called.append(path))
    monkeypatch.setattr(updater, "restart_app", lambda: called.append("restart"))
    monkeypatch.setattr(snappma, "_message", lambda *a, **k: None)
    snappma.capture()
    snappma._pending_update = "x.new"
    snappma._apply_update()
    assert called == [] and snappma._pending_update == "x.new"       # trwa zrzut: odlozone


def test_settings_dialog_builds(snappma):
    snappma.open_settings()
    dlg = snappma.dialog
    assert dlg is not None and dlg.ed_repo.text() == "NepciorLab/SnapPMa"
    dlg.reject()


def test_startup_notification_can_be_disabled(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(app_module.PrintScreenHook, "start", lambda self: True)
    monkeypatch.setattr(app_module, "UPDATE_FIRST_CHECK_MS", 10 ** 9)
    shown = []
    monkeypatch.setattr(app_module.QSystemTrayIcon, "showMessage", lambda self, *a: shown.append(a))
    settings = Settings(str(tmp_path / "t.ini"))
    first = app_module.SnapPMaApp(settings, quiet_start=False)
    first.tray.hide()
    assert len(shown) == 1
    settings.set("Program/notify_start", False)
    second = app_module.SnapPMaApp(settings, quiet_start=False)
    second.tray.hide()
    assert len(shown) == 1
