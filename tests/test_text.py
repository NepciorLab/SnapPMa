from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor

from snappma.annotations import FONT_FAMILY, FONT_SIZES, Item, text_font, text_rect
from snappma.selftest import drag, new_overlay


def start_text(ov, at):
    ov.toolbar.set_tool("text")
    ov._press(QPointF(*at), Qt.LeftButton, Qt.NoModifier)
    ov._release(QPointF(*at), Qt.LeftButton, Qt.NoModifier)


def test_font_is_arial_and_sizes_scale(qapp):
    assert FONT_FAMILY == "Arial" and text_font(24).pixelSize() == 24
    small = text_rect(Item("text", QColor("red"), 1, [QPointF(0, 0)], "Hello", 12))
    big = text_rect(Item("text", QColor("red"), 1, [QPointF(0, 0)], "Hello", 48))
    assert big.width() > 3 * small.width() and big.height() > 3 * small.height()
    two = text_rect(Item("text", QColor("red"), 1, [QPointF(0, 0)], "Hello\nWorld", 24))
    one = text_rect(Item("text", QColor("red"), 1, [QPointF(0, 0)], "Hello", 24))
    assert abs(two.height() - 2 * one.height()) < 1e-6


def test_type_commit_and_render(qapp):
    ov, res = new_overlay()
    drag(ov, (20, 20), (300, 200))
    ov.toolbar.set_font_size(32)
    start_text(ov, (60, 80))
    assert ov._editor is not None
    ov._editor.setPlainText("Hello")
    ov._editor.committed.emit()
    assert ov._editor is None and len(ov.items) == 1
    it = ov.items[0]
    assert (it.kind, it.text, it.size) == ("text", "Hello", 32) and it.points[0] == QPointF(60, 80)
    ov.copy_selection()
    img = res[0]
    reds = sum(QColor(img.pixel(x, y)).name() == "#e53935" for x in range(40, 140) for y in range(60, 100))
    assert reds > 50                                          # tekst narysowany kolorem wybranym w pasku (po przesunieciu o zaznaczenie)


def test_empty_text_is_not_added_and_escape_discards(qapp):
    ov, res = new_overlay()
    drag(ov, (20, 20), (300, 200))
    start_text(ov, (60, 80))
    ov._editor.setPlainText("   ")
    ov._editor.committed.emit()
    assert ov.items == []
    start_text(ov, (60, 80))
    ov._editor.setPlainText("keep?")
    ov._editor.discarded.emit()
    assert ov.items == [] and ov._editor is None and res == []   # Esc w edytorze nie anuluje zrzutu


def test_text_can_be_moved_with_and_without_tool(qapp):
    ov, _ = new_overlay()
    drag(ov, (20, 20), (300, 200))
    start_text(ov, (60, 80))
    ov._editor.setPlainText("Move me")
    ov._editor.committed.emit()
    drag(ov, (70, 90), (120, 140))                            # narzedzie Tekst: przeciagniecie tekstu przesuwa go
    assert ov.items[0].points[0] == QPointF(110, 130)
    ov.toolbar.set_tool(None)
    drag(ov, (120, 140), (100, 120))                          # bez narzedzia tez, a nie zaznaczenie
    assert ov.items[0].points[0] == QPointF(90, 110)
    assert (ov.sel.x(), ov.sel.y()) == (20, 20)
    drag(ov, (90, 110), (900, 900))                           # nie wychodzi poza zaznaczenie
    p = ov.items[0].points[0]
    assert p.x() <= ov.sel.x() + ov.sel.width() and p.y() <= ov.sel.y() + ov.sel.height()


def test_click_on_text_does_not_start_new_text(qapp):
    ov, _ = new_overlay()
    drag(ov, (20, 20), (300, 200))
    start_text(ov, (60, 80))
    ov._editor.setPlainText("abc")
    ov._editor.committed.emit()
    start_text(ov, (62, 84))                                  # klikniecie w istniejacy tekst: przesuwanie, nie nowy edytor
    assert ov._editor is None and len(ov.items) == 1


def test_reedit_existing_text(qapp):
    ov, _ = new_overlay()
    drag(ov, (20, 20), (300, 200))
    ov.toolbar.set_font_size(20)
    start_text(ov, (60, 80))
    ov._editor.setPlainText("one")
    ov._editor.committed.emit()
    ov.toolbar.set_tool(None)
    item = ov.items[0]
    ov._begin_text(item.points[0], item)                      # to robi dwuklik
    assert ov._editor.toPlainText() == "one"
    ov.toolbar.set_font_size(40)                              # zmiana rozmiaru dziala na edytowany tekst
    ov._editor.setPlainText("two")
    ov._editor.committed.emit()
    assert len(ov.items) == 1 and ov.items[0].text == "two" and ov.items[0].size == 40
    ov._begin_text(item.points[0], item)
    ov._editor.setPlainText("")
    ov._editor.committed.emit()
    assert ov.items == []                                     # wyczyszczony tekst znika


def test_ctrl_c_in_editor_commits_and_copies(qapp):
    ov, res = new_overlay()
    drag(ov, (20, 20), (300, 200))
    start_text(ov, (60, 80))
    ov._editor.setPlainText("done")
    ov._editor.copyRequested.emit()
    assert len(res) == 1 and res[0] is not None and len(ov.items) == 1


def test_font_size_combo_and_wheel(qapp):
    ov, _ = new_overlay()
    ov.toolbar.cmb_font.setCurrentIndex(ov.toolbar.cmb_font.findData(48))
    assert ov.state.font_size == 48
    ov.toolbar.step_font_size(-1)
    assert ov.state.font_size == FONT_SIZES[FONT_SIZES.index(48) - 1]
    ov.toolbar.set_font_size(1000)
    assert ov.state.font_size == FONT_SIZES[-1]


def test_font_size_is_persisted(qapp, tmp_path):
    from snappma.settings import Settings
    s = Settings(str(tmp_path / "t.ini"))
    assert s.get("Tools/font_size") == 20
    s.set("Tools/font_size", 32)
    assert Settings(str(tmp_path / "t.ini")).get("Tools/font_size") == 32
