"""Pelnoekranowa nakladka jednego monitora: zaznaczanie obszaru, rysowanie adnotacji, kopiowanie."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QStandardPaths, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QImage, QKeySequence, QPainter, QPen, QPixmap, QTextCursor
from PySide6.QtWidgets import QFileDialog, QFrame, QMessageBox, QPlainTextEdit, QWidget

from .annotations import (Item, ToolState, constrain_axis, constrain_square, is_degenerate, paint_item,
                          render_result, save_jpeg, text_font, text_rect)
from .i18n import tr
from .toolbar import Toolbar
from .version import APP_NAME

ACCENT = QColor("#2D8CFF")
HANDLE_HIT = 8          # promien chwytania uchwytu (piksele okna)
HANDLE_DRAW = 3         # polowa boku rysowanego uchwytu
MIN_SELECTION = 4       # mniejsze zaznaczenie jest odrzucane
HANDLE_CURSORS = {
    "tl": Qt.SizeFDiagCursor, "br": Qt.SizeFDiagCursor, "tr": Qt.SizeBDiagCursor, "bl": Qt.SizeBDiagCursor,
    "t": Qt.SizeVerCursor, "b": Qt.SizeVerCursor, "l": Qt.SizeHorCursor, "r": Qt.SizeHorCursor,
}


def rect_from_edges(x1: int, y1: int, x2: int, y2: int) -> QRect:
    return QRect(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))


class TextEditor(QPlainTextEdit):
    """Edytor tekstu wpisywanego na zrzucie. Enter zatwierdza, Shift+Enter nowa linia, Esc odrzuca,
    Ctrl+C bez zaznaczenia tekstu zatwierdza tekst i kopiuje zrzut."""
    committed = Signal()
    discarded = Signal()
    copyRequested = Signal()

    def __init__(self, parent):
        super().__init__(parent)
        self.setFrameStyle(QFrame.NoFrame)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.document().setDocumentMargin(0)
        self.setCursor(Qt.IBeamCursor)

    def keyPressEvent(self, ev) -> None:
        if ev.key() == Qt.Key_Escape:
            self.discarded.emit()
        elif ev.key() in (Qt.Key_Return, Qt.Key_Enter) and not ev.modifiers() & Qt.ShiftModifier:
            self.committed.emit()
        elif ev.matches(QKeySequence.Copy) and not self.textCursor().hasSelection():
            self.copyRequested.emit()
        else:
            super().keyPressEvent(ev)


class CaptureOverlay(QWidget):
    finished = Signal(object)       # QImage (skopiowano) albo None (anulowano)
    started = Signal()              # uzytkownik zaczal zaznaczac na tym monitorze
    saved = Signal(str)             # zrzut zapisano do pliku JPG (sciezka)

    def __init__(self, screen, shot: QImage, state: ToolState):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setAttribute(Qt.WA_QuitOnClose, False)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)
        self.screen_obj = screen
        self.state = state
        self.shot = shot                                    # piksele fizyczne, bez skali
        self._pm = QPixmap.fromImage(shot)
        self._dim = QPixmap(self._pm)
        p = QPainter(self._dim)
        p.fillRect(self._dim.rect(), QColor(0, 0, 0, 115))
        p.end()

        self.sel: QRect | None = None
        self.phase = "select"                               # select | edit
        self.items: list[Item] = []
        self._current: Item | None = None
        self._mode: str | None = None                       # new | move | resize:<uchwyt> | draw
        self._anchor = QPoint()
        self._sel0 = QRect()
        self._prev_sel: QRect | None = None
        self._grab_offset = QPointF()
        self._drag_item: Item | None = None                 # przesuwany tekst
        self._editor: TextEditor | None = None
        self._editing: Item | None = None                   # istniejacy tekst edytowany ponownie
        self._text_origin = QPointF()

        self.toolbar = Toolbar(state, self)
        self.toolbar.hide()
        self.toolbar.undo.connect(self.undo)
        self.toolbar.copy.connect(self.copy_selection)
        self.toolbar.cancel.connect(self.cancel)
        self.toolbar.save.connect(self.save_selection)
        self.toolbar.toolChanged.connect(lambda _t: self._update_cursor(None))
        self.toolbar.styleChanged.connect(self._style_changed)

    # ---------- wyswietlenie ----------
    def show_on_screen(self) -> None:
        self.winId()
        handle = self.windowHandle()
        if handle is not None:
            handle.setScreen(self.screen_obj)
        self.setGeometry(self.screen_obj.geometry())
        self.show()

    def _scale(self) -> tuple[float, float]:
        return self.shot.width() / max(1, self.width()), self.shot.height() / max(1, self.height())

    def paintEvent(self, _ev) -> None:
        p = QPainter(self)
        p.drawPixmap(self.rect(), self._dim)
        sel = self.sel
        if sel is None or sel.width() <= 0 or sel.height() <= 0:
            if self.sel is None:
                self._draw_hint(p)
            return
        fx, fy = self._scale()
        p.drawPixmap(QRectF(sel), self._pm, QRectF(sel.x() * fx, sel.y() * fy, sel.width() * fx, sel.height() * fy))
        p.save()
        p.setClipRect(sel)
        for it in self.items:
            if it is not self._editing:
                paint_item(p, it)
        if self._current is not None:
            paint_item(p, self._current)
        p.restore()
        p.setRenderHint(QPainter.Antialiasing, False)
        p.setPen(QPen(ACCENT, 1))
        p.setBrush(Qt.NoBrush)
        p.drawRect(sel.adjusted(-1, -1, 0, 0))
        self._draw_label(p, sel, fx, fy)
        if self.phase == "edit" and self._mode != "new":
            self._draw_handles(p)

    def _draw_hint(self, p: QPainter) -> None:
        text = tr("Drag to select the area to capture. Esc cancels.")
        fm = p.fontMetrics()
        w, h = fm.horizontalAdvance(text) + 28, fm.height() + 16
        r = QRect((self.width() - w) // 2, 24, w, h)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(20, 20, 20, 215))
        p.drawRoundedRect(r, 8, 8)
        p.setPen(QColor("#F2F2F2"))
        p.drawText(r, Qt.AlignCenter, text)

    def _draw_label(self, p: QPainter, sel: QRect, fx: float, fy: float) -> None:
        text = f"{round(sel.width() * fx)} × {round(sel.height() * fy)}"
        fm = p.fontMetrics()
        w, h = fm.horizontalAdvance(text) + 12, fm.height() + 6
        x, y = sel.x(), sel.y() - h - 4
        if y < 0:
            x, y = sel.x() + 4, sel.y() + 4
        r = QRect(x, y, w, h)
        p.fillRect(r, QColor(0, 0, 0, 175))
        p.setPen(QColor("#FFFFFF"))
        p.drawText(r, Qt.AlignCenter, text)

    def _draw_handles(self, p: QPainter) -> None:
        p.setPen(QPen(ACCENT, 1))
        p.setBrush(QColor("#FFFFFF"))
        for x, y in self._handle_points().values():
            p.drawRect(QRectF(x - HANDLE_DRAW, y - HANDLE_DRAW, 2 * HANDLE_DRAW, 2 * HANDLE_DRAW))

    # ---------- uchwyty zaznaczenia ----------
    def _handle_points(self) -> dict[str, tuple[float, float]]:
        s = self.sel
        x1, y1, x2, y2 = s.x(), s.y(), s.x() + s.width(), s.y() + s.height()
        xm, ym = (x1 + x2) / 2, (y1 + y2) / 2
        return {"tl": (x1, y1), "tr": (x2, y1), "br": (x2, y2), "bl": (x1, y2),
                "t": (xm, y1), "r": (x2, ym), "b": (xm, y2), "l": (x1, ym)}

    def _handle_at(self, pos: QPointF) -> str | None:
        if self.phase != "edit" or self.sel is None:
            return None
        for name, (x, y) in self._handle_points().items():
            if abs(pos.x() - x) <= HANDLE_HIT and abs(pos.y() - y) <= HANDLE_HIT:
                return name
        return None

    def _clamp_point(self, pos: QPointF) -> QPoint:
        return QPoint(min(max(round(pos.x()), 0), self.width()), min(max(round(pos.y()), 0), self.height()))

    def _clamp_to_sel(self, pos: QPointF) -> QPointF:
        s = self.sel
        return QPointF(min(max(pos.x(), s.x()), s.x() + s.width()), min(max(pos.y(), s.y()), s.y() + s.height()))

    def _resized(self, handle: str, pos: QPointF) -> QRect:
        s0 = self._sel0
        x1, y1, x2, y2 = s0.x(), s0.y(), s0.x() + s0.width(), s0.y() + s0.height()
        mp = self._clamp_point(pos)
        if "l" in handle:
            x1 = mp.x()
        if "r" in handle:
            x2 = mp.x()
        if "t" in handle:
            y1 = mp.y()
        if "b" in handle:
            y2 = mp.y()
        return rect_from_edges(x1, y1, x2, y2)

    # ---------- mysz ----------
    def mousePressEvent(self, ev) -> None:
        self._press(ev.position(), ev.button(), ev.modifiers())

    def mouseMoveEvent(self, ev) -> None:
        self._move(ev.position(), ev.modifiers(), bool(ev.buttons() & Qt.LeftButton))

    def mouseReleaseEvent(self, ev) -> None:
        self._release(ev.position(), ev.button(), ev.modifiers())

    def wheelEvent(self, ev) -> None:
        if self.phase == "edit":
            step = 1 if ev.angleDelta().y() > 0 else -1
            if self.state.tool == "text":
                self.toolbar.step_font_size(step)
            else:
                self.toolbar.set_width(self.state.width + step)
            self.update()

    def _press(self, pos: QPointF, button, mods) -> None:
        if button == Qt.RightButton and self.phase == "select":
            self.cancel()
            return
        if button != Qt.LeftButton:
            return
        if self._editor is not None:                     # klikniecie poza edytorem zatwierdza tekst
            self._commit_text()
            return
        self.setFocus()
        if self.phase == "select":
            self._begin_new(pos)
            return
        handle = self._handle_at(pos)
        inside = self.sel.contains(pos.toPoint())
        if handle:
            self._mode, self._sel0 = "resize:" + handle, QRect(self.sel)
            self.toolbar.hide()
        elif inside and self.state.tool in (None, "text") and self._text_at(pos) is not None:
            item = self._text_at(pos)
            self._mode, self._drag_item = "move_text", item
            self._grab_offset = item.points[0] - pos
        elif self.state.tool == "text" and inside:
            self._begin_text(self._clamp_to_sel(pos))
        elif self.state.tool and inside:
            self._begin_item(pos, mods)
        elif self.state.tool:
            return                                       # z narzedziem poza zaznaczeniem nic nie robimy
        elif inside:
            self._mode, self._sel0, self._anchor = "move", QRect(self.sel), pos.toPoint()
            self.toolbar.hide()
        else:
            self._prev_sel = QRect(self.sel)
            self._begin_new(pos)

    def _begin_new(self, pos: QPointF) -> None:
        self._mode = "new"
        self._anchor = self._clamp_point(pos)
        self.sel = QRect(self._anchor.x(), self._anchor.y(), 0, 0)
        self.toolbar.hide()
        self.started.emit()
        self.update()

    def _begin_item(self, pos: QPointF, mods) -> None:
        self._mode = "draw"
        p = self._clamp_to_sel(pos)
        kind = self.state.tool
        pts = [p] if kind in ("pen", "pointer") else [p, QPointF(p)]
        self._current = Item(kind, QColor(self.state.color), self.state.width, pts)
        self.update()

    def _move(self, pos: QPointF, mods, pressed: bool) -> None:
        if not pressed or self._mode is None:
            self._update_cursor(pos)
            return
        if self._mode == "new":
            a, b = self._anchor, self._clamp_point(pos)
            self.sel = rect_from_edges(a.x(), a.y(), b.x(), b.y())
        elif self._mode == "move":
            d = pos.toPoint() - self._anchor
            r = QRect(self._sel0)
            r.translate(d)
            r.moveLeft(min(max(r.x(), 0), self.width() - r.width()))
            r.moveTop(min(max(r.y(), 0), self.height() - r.height()))
            self.sel = r
        elif self._mode == "move_text" and self._drag_item is not None:
            self._drag_item.points = [self._clamp_to_sel(pos + self._grab_offset)]
        elif self._mode.startswith("resize"):
            self.sel = self._resized(self._mode.split(":")[1], pos)
        elif self._mode == "draw" and self._current is not None:
            self._extend_item(self._clamp_to_sel(pos), bool(mods & Qt.ShiftModifier))
        self.update()

    def _extend_item(self, p: QPointF, shift: bool) -> None:
        it = self._current
        if it.kind == "pen":
            if it.points[-1] != p:
                it.points.append(p)
        elif it.kind == "pointer":
            it.points = [p]
        else:
            start = it.points[0]
            if shift:
                p = constrain_square(start, p) if it.kind == "rect" else constrain_axis(start, p)
                p = self._clamp_to_sel(p)
            it.points = [start, p]

    def _release(self, pos: QPointF, button, mods) -> None:
        if button != Qt.LeftButton or self._mode is None:
            return
        mode, self._mode = self._mode, None
        if mode == "move_text":
            self._drag_item = None
        elif mode == "draw":
            it, self._current = self._current, None
            if it is not None and not is_degenerate(it):
                self.items.append(it)
        elif mode == "new":
            if self.sel.width() < MIN_SELECTION or self.sel.height() < MIN_SELECTION:
                self.sel, self._prev_sel = (self._prev_sel, None) if self._prev_sel else (None, None)
                if self.sel is None:
                    self.phase = "select"
            else:
                self.phase, self._prev_sel = "edit", None
        elif mode.startswith("resize") and (self.sel.width() < 1 or self.sel.height() < 1):
            self.sel = self._sel0
        if self.phase == "edit":
            self._show_toolbar()
        self._update_cursor(pos)
        self.update()

    def _update_cursor(self, pos: QPointF | None) -> None:
        if self.phase == "select":
            self.setCursor(Qt.CrossCursor)
            return
        if pos is None:
            pos = QPointF(self.mapFromGlobal(QCursor.pos()))
        handle = self._handle_at(pos)
        if handle:
            self.setCursor(HANDLE_CURSORS[handle])
        elif self.state.tool in (None, "text") and self.sel.contains(pos.toPoint()) and self._text_at(pos) is not None:
            self.setCursor(Qt.SizeAllCursor)
        elif self.state.tool == "text":
            self.setCursor(Qt.IBeamCursor if self.sel.contains(pos.toPoint()) else Qt.ArrowCursor)
        elif self.state.tool:
            self.setCursor(Qt.CrossCursor if self.sel.contains(pos.toPoint()) else Qt.ArrowCursor)
        else:
            self.setCursor(Qt.SizeAllCursor if self.sel.contains(pos.toPoint()) else Qt.CrossCursor)

    # ---------- pasek narzedzi ----------
    def _show_toolbar(self) -> None:
        tb, s = self.toolbar, self.sel
        tb.adjustSize()
        w, h = tb.width(), tb.height()
        x = min(max(s.x() + s.width() - w, 4), max(4, self.width() - w - 4))
        y = s.y() + s.height() + 8
        if y + h > self.height() - 4:
            y = s.y() - h - 8
            if y < 4:
                y = max(4, s.y() + s.height() - h - 8)
        tb.move(x, y)
        tb.show()
        tb.raise_()

    # ---------- tekst ----------
    def mouseDoubleClickEvent(self, ev) -> None:
        pos = ev.position()
        if self.phase == "edit" and ev.button() == Qt.LeftButton and self._editor is None \
                and self.state.tool in (None, "text") and self.sel.contains(pos.toPoint()):
            item = self._text_at(pos)
            if item is not None:
                self._mode, self._drag_item = None, None
                self._begin_text(item.points[0], item)
                return
        self._press(pos, ev.button(), ev.modifiers())

    def _text_at(self, pos: QPointF) -> Item | None:
        for it in reversed(self.items):
            if it.kind == "text" and it is not self._editing and text_rect(it).adjusted(-3, -3, 3, 3).contains(pos):
                return it
        return None

    def _begin_text(self, pos: QPointF, item: Item | None = None) -> None:
        self._text_origin = QPointF(pos)
        self._editing = item
        if item is not None:                             # pasek pokazuje ustawienia edytowanego tekstu
            self.toolbar.set_color(item.color)
            self.toolbar.set_font_size(item.size)
        ed = TextEditor(self)
        ed.setPlainText(item.text if item is not None else "")
        ed.committed.connect(self._commit_text)
        ed.discarded.connect(self._discard_text)
        ed.copyRequested.connect(self.copy_selection)
        ed.textChanged.connect(self._fit_editor)
        self._editor = ed
        self._style_editor()
        ed.show()
        ed.setFocus()
        ed.moveCursor(QTextCursor.End)
        self.update()

    def _style_editor(self) -> None:
        ed = self._editor
        if ed is None:
            return
        ed.setFont(text_font(self.state.font_size))
        ed.setStyleSheet(f"QPlainTextEdit {{ color: {self.state.color.name()}; background: rgba(0, 0, 0, 70);"
                         f" border: 1px dashed #2D8CFF; padding: 0px; }}")
        self._fit_editor()

    def _fit_editor(self) -> None:
        ed = self._editor
        if ed is None:
            return
        r = text_rect(Item("text", self.state.color, 1, [self._text_origin], ed.toPlainText(), self.state.font_size))
        ed.setGeometry(round(r.x()) - 1, round(r.y()) - 1, max(24, round(r.width()) + 16), round(r.height()) + 4)

    def _style_changed(self) -> None:
        self._style_editor()

    def _close_editor(self) -> None:
        ed, self._editor = self._editor, None
        if ed is not None:
            ed.hide()
            ed.deleteLater()

    def _commit_text(self) -> None:
        ed = self._editor
        if ed is None:
            return
        text = ed.toPlainText().rstrip("\n")
        self._close_editor()
        item, self._editing = self._editing, None
        if item is not None:
            if text.strip():
                item.text, item.color, item.size = text, QColor(self.state.color), self.state.font_size
            elif item in self.items:
                self.items.remove(item)                  # wyczyszczony tekst znika
        elif text.strip():
            self.items.append(Item("text", QColor(self.state.color), self.state.width, [self._text_origin],
                                   text, self.state.font_size))
        self.setFocus()
        self.update()

    def _discard_text(self) -> None:
        self._close_editor()
        self._editing = None
        self.setFocus()
        self.update()

    # ---------- klawiatura i wynik ----------
    def keyPressEvent(self, ev) -> None:
        if ev.key() == Qt.Key_Escape:
            if self._editor is not None:
                self._discard_text()
            else:
                self.cancel()
        elif ev.matches(QKeySequence.Copy) and self.phase == "edit":
            self.copy_selection()
        elif ev.matches(QKeySequence.Save) and self.phase == "edit":
            self.save_selection()
        elif ev.matches(QKeySequence.Undo):
            self.undo()
        else:
            super().keyPressEvent(ev)

    def undo(self) -> None:
        if self._editor is not None:
            self._discard_text()
        elif self.items:
            self.items.pop()
            self.update()

    def cancel(self) -> None:
        self.finished.emit(None)

    def _ask_save_path(self) -> str:
        """Okno wyboru pliku (w testach podmieniane)."""
        folder = self.state.save_dir or QStandardPaths.writableLocation(QStandardPaths.PicturesLocation) \
            or str(Path.home())
        name = f"{APP_NAME}_{datetime.now():%Y-%m-%d_%H-%M-%S}.jpg"
        path, _ = QFileDialog.getSaveFileName(self, tr("Save screenshot as JPG"), str(Path(folder) / name),
                                              tr("JPEG image (*.jpg *.jpeg)"))
        return path

    def save_selection(self) -> None:
        """Zapisuje zaznaczony fragment z adnotacjami jako JPG i konczy zrzut; anulowanie okna zostawia edycje."""
        if self._editor is not None:
            self._commit_text()
        if self.phase != "edit" or self.sel is None:
            return
        path = self._ask_save_path()
        self.activateWindow()
        self.setFocus()
        if not path:
            return
        img = render_result(self.shot, self.sel, self.size(), self.items)
        try:
            path = save_jpeg(img, path, self.state.jpeg_quality)
        except OSError as exc:
            QMessageBox.warning(self, APP_NAME, f"{tr('Could not save the file.')}\n{exc}")
            return
        self.state.save_dir = str(Path(path).parent)
        self.saved.emit(path)

    def copy_selection(self) -> None:
        if self._editor is not None:
            self._commit_text()
        if self.phase != "edit" or self.sel is None:
            return
        self.finished.emit(render_result(self.shot, self.sel, self.size(), self.items))
