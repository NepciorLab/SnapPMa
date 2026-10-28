from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor

from snappma import selftest
from snappma.selftest import drag, new_overlay


def test_selftest_all_ok(qapp, tmp_path):
    out = tmp_path / "r.txt"
    assert selftest.run(str(out)) == 0
    assert "ALL OK" in out.read_text(encoding="utf-8")


def test_too_small_selection_is_discarded(qapp):
    ov, _ = new_overlay()
    drag(ov, (10, 10), (12, 12))
    assert ov.phase == "select" and ov.sel is None


def test_copy_needs_selection(qapp):
    ov, res = new_overlay()
    ov.copy_selection()
    assert res == []


def test_cancel(qapp):
    ov, res = new_overlay()
    ov.cancel()
    assert res == [None]


def test_right_click_cancels_in_select_phase(qapp):
    ov, res = new_overlay()
    ov._press(QPointF(5, 5), Qt.RightButton, Qt.NoModifier)
    assert res == [None]


def test_resize_and_move_selection(qapp):
    ov, _ = new_overlay()
    drag(ov, (50, 50), (150, 150))
    drag(ov, (150, 150), (200, 180))                         # uchwyt prawego dolnego rogu
    assert (ov.sel.width(), ov.sel.height()) == (150, 130)
    drag(ov, (100, 100), (130, 110))                         # wnetrze bez narzedzia przesuwa
    assert (ov.sel.x(), ov.sel.y()) == (80, 60) and (ov.sel.width(), ov.sel.height()) == (150, 130)
    drag(ov, (80, 125), (60, 125))                           # lewa krawedz (uchwyt w polowie)
    assert ov.sel.x() == 60 and ov.sel.width() == 170


def test_selection_is_clamped_to_screen(qapp):
    ov, _ = new_overlay()
    drag(ov, (300, 200), (900, 700))
    assert ov.sel.x() + ov.sel.width() <= selftest.W and ov.sel.y() + ov.sel.height() <= selftest.H


def test_drawing_requires_start_inside_selection(qapp):
    ov, _ = new_overlay()
    drag(ov, (50, 50), (150, 150))
    ov.toolbar.set_tool("rect")
    drag(ov, (200, 200), (250, 250))                         # poza zaznaczeniem: nic
    assert ov.items == [] and ov.sel.width() == 100


def test_pen_and_arrow_are_clipped_and_rendered(qapp):
    ov, res = new_overlay()
    drag(ov, (50, 50), (150, 150))
    ov.toolbar.set_width(6)
    ov.toolbar.set_tool("pen")
    ov._press(QPointF(60, 60), Qt.LeftButton, Qt.NoModifier)
    for x in range(60, 400, 20):                             # wyjscie poza zaznaczenie jest przycinane do niego
        ov._move(QPointF(x, 100), Qt.NoModifier, True)
    ov._release(QPointF(399, 100), Qt.LeftButton, Qt.NoModifier)
    assert max(p.x() for p in ov.items[0].points) <= 150
    ov.toolbar.set_tool("arrow")
    drag(ov, (60, 140), (140, 80), Qt.ShiftModifier)         # Shift: pozioma
    a = ov.items[1]
    assert a.points[0].y() == a.points[1].y() == 140
    ov.copy_selection()
    img = res[0]
    assert (img.width(), img.height()) == (100, 100)
    assert QColor(img.pixel(40, 50)).name() == "#e53935"     # slad olowka
    assert QColor(img.pixel(5, 5)).name() == "#ffffff"


def test_tool_toggle_and_state_shared(qapp):
    ov, _ = new_overlay()
    ov.toolbar.tool_buttons["line"].click()
    assert ov.state.tool == "line"
    ov.toolbar.tool_buttons["line"].click()
    assert ov.state.tool is None
    ov.toolbar.swatches[4].click()
    assert ov.state.color.name() == "#1e88e5"
    ov.toolbar.slider.setValue(12)
    assert ov.state.width == 12


def test_toolbar_stays_inside_screen(qapp):
    ov, _ = new_overlay()
    drag(ov, (5, 5), (selftest.W - 5, selftest.H - 5))      # zaznaczony prawie caly ekran
    tb = ov.toolbar
    assert tb.x() >= 4 and tb.y() >= 4


def test_pointer_is_always_white_with_black_outline(qapp):
    ov, res = new_overlay()
    ov.toolbar.set_width(10)
    drag(ov, (50, 50), (250, 200))
    ov.toolbar.set_tool("pointer")
    drag(ov, (100, 80), (100, 80))                          # czerwony kolor wybrany, kursor i tak bialy
    ov.copy_selection()
    img = res[0]
    names = {QColor(img.pixel(x, y)).name() for x in range(50, 70) for y in range(30, 60)}
    assert "#ffffff" in names and "#000000" in names and "#e53935" not in names
