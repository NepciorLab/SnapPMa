"""Pasek narzedzi nad zrzutem: narzedzia, kolor, grubosc, cofnij, kopiuj, anuluj."""
from __future__ import annotations

from functools import partial

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QColorDialog, QComboBox, QFrame, QHBoxLayout, QLabel, QSlider, QToolButton, QWidget

from .annotations import FONT_SIZES, MAX_WIDTH, MIN_WIDTH, PRESET_COLORS, ToolState
from .i18n import tr
from .icons import tool_icon

STYLE = """
QFrame#bar { background: rgba(34, 34, 34, 240); border: 1px solid #5a5a5a; border-radius: 9px; }
QToolButton { background: transparent; border: none; border-radius: 6px; padding: 4px; }
QToolButton:hover { background: #4a4a4a; }
QToolButton:checked { background: #2d8cff; }
QLabel { color: #e6e6e6; }
QComboBox { background: #3a3a3a; color: #f2f2f2; border: 1px solid #666; border-radius: 4px; padding: 2px 6px; min-width: 34px; }
QComboBox::drop-down { border: none; width: 14px; }
QComboBox QAbstractItemView { background: #2b2b2b; color: #f2f2f2; selection-background-color: #2d8cff; }
QSlider::groove:horizontal { height: 4px; background: #6a6a6a; border-radius: 2px; }
QSlider::handle:horizontal { background: #f2f2f2; width: 12px; margin: -5px 0; border-radius: 6px; }
QSlider::sub-page:horizontal { background: #2d8cff; border-radius: 2px; }
"""


def tool_defs() -> list[tuple[str, str]]:
    return [
        ("pen", tr("Pen (freehand)")),
        ("line", tr("Line (hold Shift: horizontal / vertical)")),
        ("arrow", tr("Arrow (hold Shift: horizontal / vertical)")),
        ("rect", tr("Rectangle")),
        ("text", tr("Text (click and type; Enter confirms, Shift+Enter new line; drag to move, double-click to edit)")),
        ("pointer", tr("Mouse pointer arrow")),
    ]


class Swatch(QToolButton):
    """Okragly przycisk koloru; zaznaczony ma biala obwodke."""

    def __init__(self, color: QColor, size: int = 22, parent=None):
        super().__init__(parent)
        self.color = QColor(color)
        self.selected = False
        self.setFixedSize(size, size)
        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, _ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(3, 3, -3, -3)
        p.setPen(QPen(QColor("#ffffff") if self.selected else QColor("#8a8a8a"), 2.2 if self.selected else 1.0))
        p.setBrush(self.color)
        p.drawEllipse(r)


class WidthDot(QWidget):
    """Podglad grubosci i koloru linii."""

    def __init__(self, state: ToolState, parent=None):
        super().__init__(parent)
        self.state = state
        self.setFixedSize(34, 34)

    def paintEvent(self, _ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        d = min(float(self.state.width), 30.0)
        p.setPen(QPen(QColor("#8a8a8a"), 1.0))
        p.setBrush(self.state.color)
        c = self.rect().center()
        p.drawEllipse(QRectF(c.x() + 0.5 - d / 2, c.y() + 0.5 - d / 2, d, d))


class Toolbar(QFrame):
    toolChanged = Signal(object)        # nazwa narzedzia albo None
    styleChanged = Signal()             # zmiana koloru, grubosci albo rozmiaru czcionki
    undo = Signal()
    copy = Signal()
    cancel = Signal()

    def __init__(self, state: ToolState, parent=None):
        super().__init__(parent)
        self.state = state
        self.setObjectName("bar")
        self.setStyleSheet(STYLE)
        self.setFocusPolicy(Qt.NoFocus)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(4)

        self.tool_buttons: dict[str, QToolButton] = {}
        for name, tip in tool_defs():
            b = self._button(name, tip, checkable=True)
            b.clicked.connect(partial(self._on_tool, name))
            self.tool_buttons[name] = b
            lay.addWidget(b)
        lay.addWidget(self._separator())
        self.btn_undo = self._button("undo", tr("Undo (Ctrl+Z)"))
        self.btn_undo.clicked.connect(lambda *_: self.undo.emit())
        lay.addWidget(self.btn_undo)
        lay.addWidget(self._separator())

        self.swatches: list[Swatch] = []
        for hexcolor in PRESET_COLORS:
            s = Swatch(QColor(hexcolor))
            s.setToolTip(tr("Color"))
            s.clicked.connect(partial(self.set_color, QColor(hexcolor)))
            self.swatches.append(s)
            lay.addWidget(s)
        self.btn_custom = QToolButton()
        self.btn_custom.setText("…")
        self.btn_custom.setToolTip(tr("Custom color…"))
        self.btn_custom.setFocusPolicy(Qt.NoFocus)
        self.btn_custom.setStyleSheet("QToolButton { color: #f2f2f2; font-weight: bold; }")
        self.btn_custom.clicked.connect(lambda *_: self._custom_color())
        lay.addWidget(self.btn_custom)
        lay.addWidget(self._separator())

        self.dot = WidthDot(state)
        lay.addWidget(self.dot)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(MIN_WIDTH, MAX_WIDTH)
        self.slider.setValue(state.width)
        self.slider.setFixedWidth(90)
        self.slider.setFocusPolicy(Qt.NoFocus)
        self.slider.setToolTip(tr("Line width"))
        self.slider.valueChanged.connect(self.set_width)
        lay.addWidget(self.slider)
        self.lbl_width = QLabel(str(state.width))
        self.lbl_width.setFixedWidth(22)
        lay.addWidget(self.lbl_width)
        lay.addWidget(self._separator())

        self.cmb_font = QComboBox()
        for size in FONT_SIZES:
            self.cmb_font.addItem(str(size), size)
        self.cmb_font.setFocusPolicy(Qt.NoFocus)
        self.cmb_font.setToolTip(tr("Text size (Arial)"))
        self.cmb_font.currentIndexChanged.connect(lambda *_: self.set_font_size(self.cmb_font.currentData()))
        lay.addWidget(self.cmb_font)
        lay.addWidget(self._separator())

        self.btn_copy = self._button("copy", tr("Copy to clipboard (Ctrl+C)"))
        self.btn_copy.clicked.connect(lambda *_: self.copy.emit())
        lay.addWidget(self.btn_copy)
        self.btn_cancel = self._button("cancel", tr("Cancel (Esc)"))
        self.btn_cancel.clicked.connect(lambda *_: self.cancel.emit())
        lay.addWidget(self.btn_cancel)
        self.refresh()

    def _button(self, icon: str, tip: str, checkable: bool = False) -> QToolButton:
        b = QToolButton()
        b.setIcon(tool_icon(icon))
        b.setIconSize(QSize(24, 24))
        b.setToolTip(tip)
        b.setCheckable(checkable)
        b.setFixedSize(34, 34)
        b.setFocusPolicy(Qt.NoFocus)
        return b

    @staticmethod
    def _separator() -> QFrame:
        f = QFrame()
        f.setFixedWidth(1)
        f.setFixedHeight(24)
        f.setStyleSheet("background: #666;")
        return f

    def _on_tool(self, name: str, *_) -> None:
        self.set_tool(None if self.state.tool == name else name)

    def set_tool(self, name: str | None) -> None:
        self.state.tool = name
        self.refresh()
        self.toolChanged.emit(name)

    def set_color(self, color: QColor, *_) -> None:
        self.state.color = QColor(color)
        self.refresh()
        self.styleChanged.emit()

    def set_width(self, value: int) -> None:
        self.state.width = max(MIN_WIDTH, min(MAX_WIDTH, int(value)))
        if self.slider.value() != self.state.width:
            self.slider.setValue(self.state.width)
        self.refresh()
        self.styleChanged.emit()

    def set_font_size(self, value: int) -> None:
        size = min(FONT_SIZES, key=lambda s: abs(s - int(value)))
        self.state.font_size = size
        self.refresh()
        self.styleChanged.emit()

    def step_font_size(self, step: int) -> None:
        idx = FONT_SIZES.index(self.state.font_size) + step
        self.set_font_size(FONT_SIZES[max(0, min(len(FONT_SIZES) - 1, idx))])

    def _custom_color(self) -> None:
        win = self.window()
        color = QColorDialog.getColor(self.state.color, win, tr("Custom color…"))
        win.activateWindow()
        win.setFocus()
        if color.isValid():
            self.set_color(color)

    def refresh(self) -> None:
        for name, b in self.tool_buttons.items():
            b.setChecked(self.state.tool == name)
        for s in self.swatches:
            s.selected = s.color.rgb() == self.state.color.rgb()
            s.update()
        self.lbl_width.setText(str(self.state.width))
        idx = self.cmb_font.findData(self.state.font_size)
        if idx >= 0 and idx != self.cmb_font.currentIndex():
            self.cmb_font.blockSignals(True)
            self.cmb_font.setCurrentIndex(idx)
            self.cmb_font.blockSignals(False)
        self.dot.update()

    # klikniecie w pusty fragment paska nie moze trafic do nakladki (zaczelo by zaznaczanie albo rysowanie)
    def mousePressEvent(self, ev) -> None:
        ev.accept()

    def mouseMoveEvent(self, ev) -> None:
        ev.accept()

    def mouseReleaseEvent(self, ev) -> None:
        ev.accept()
