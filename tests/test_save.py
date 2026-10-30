from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QMessageBox

from snappma import overlay as overlay_module
from snappma.annotations import save_jpeg
from snappma.selftest import drag, new_overlay


def selected_overlay():
    ov, res = new_overlay()
    drag(ov, (50, 40), (250, 190))                       # 200 x 150
    saved = []
    ov.saved.connect(saved.append)
    return ov, res, saved


def test_save_jpeg_appends_extension_and_clamps_quality(qapp, tmp_path):
    img = QImage(40, 30, QImage.Format_RGB32)
    img.fill(QColor("#336699"))
    path = save_jpeg(img, str(tmp_path / "shot"), 500)
    assert path.endswith(".jpg") and QImage(path).width() == 40
    assert save_jpeg(img, str(tmp_path / "b.JPEG"), 0).endswith("b.JPEG")        # istniejace rozszerzenie zostaje


def test_save_selection_writes_jpg_with_annotations(qapp, tmp_path):
    ov, res, saved = selected_overlay()
    target = str(tmp_path / "out.jpg")
    ov._ask_save_path = lambda: target
    ov.toolbar.set_width(6)
    ov.toolbar.set_tool("line")
    drag(ov, (60, 100), (200, 100))
    ov.save_selection()
    assert saved == [target] and res == []               # zapis nie kopiuje do schowka
    img = QImage(target)
    assert (img.width(), img.height()) == (200, 150)
    c = QColor(img.pixel(80, 60))
    assert c.red() > 200 and c.green() < 90              # czerwona linia (JPG jest stratny, wiec z tolerancja)
    assert QColor(img.pixel(5, 5)).name() == "#ffffff"
    assert ov.state.save_dir == str(tmp_path)


def test_cancelled_dialog_keeps_editing(qapp, tmp_path):
    ov, res, saved = selected_overlay()
    ov._ask_save_path = lambda: ""
    ov.save_selection()
    assert saved == [] and res == [] and ov.phase == "edit"


def test_save_error_is_reported_not_raised(qapp, tmp_path, monkeypatch):
    ov, res, saved = selected_overlay()
    ov._ask_save_path = lambda: str(tmp_path / "no_such_dir" / "x.jpg")
    warned = []
    monkeypatch.setattr(overlay_module.QMessageBox, "warning", lambda *a: warned.append(a))
    ov.save_selection()
    assert saved == [] and len(warned) == 1


def test_save_without_selection_does_nothing(qapp):
    ov, res = new_overlay()
    ov._ask_save_path = lambda: (_ for _ in ()).throw(AssertionError("dialog must not open"))
    ov.save_selection()
    assert res == []


def test_save_commits_pending_text_first(qapp, tmp_path):
    ov, res, saved = selected_overlay()
    ov._ask_save_path = lambda: str(tmp_path / "t.jpg")
    ov.toolbar.set_tool("text")
    ov._press(QPointF(70, 60), Qt.LeftButton, Qt.NoModifier)
    ov._release(QPointF(70, 60), Qt.LeftButton, Qt.NoModifier)
    ov._editor.setPlainText("saved text")
    ov.save_selection()
    assert len(ov.items) == 1 and len(saved) == 1


def test_save_button_and_session_close(qapp, tmp_path, monkeypatch):
    from snappma import session as session_module
    from snappma.annotations import ToolState
    monkeypatch.setattr(session_module, "bring_to_front", lambda w: None)
    session = session_module.CaptureSession(ToolState())
    got = []
    session.saved.connect(got.append)
    session.start()
    ov = session.overlays[0]
    drag(ov, (20, 20), (120, 90))
    target = str(tmp_path / "s.jpg")
    ov._ask_save_path = lambda: target
    ov.toolbar.btn_save.click()
    assert got == [target] and not session.active
