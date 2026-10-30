"""Adnotacje (olowek, linia, strzalka, prostokat, kursor myszy) i zlozenie wyniku. Bez zaleznosci od okien."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QPainter, QPainterPath, QPen, QPolygonF

TOOLS = ("pen", "line", "arrow", "rect", "text", "pointer")
PRESET_COLORS = ("#E53935", "#FB8C00", "#FDD835", "#43A047", "#1E88E5", "#000000", "#FFFFFF")
MIN_WIDTH, MAX_WIDTH = 1, 30
FONT_FAMILY = "Arial"
FONT_SIZES = (10, 12, 14, 16, 18, 20, 24, 28, 32, 40, 48, 64, 72, 96)     # piksele; domyslnie 20
DEFAULT_FONT_SIZE = 20

# Ksztalt kursora myszy (czubek w 0,0), wysokosc ok. 18,6 jednostek.
POINTER_SHAPE = ((0.0, 0.0), (0.0, 16.0), (3.6, 12.4), (6.2, 18.6), (8.6, 17.6), (6.0, 11.6), (11.0, 11.6))
POINTER_HEIGHT = 18.6


class ToolState:
    """Wspolne ustawienia narzedzi dla wszystkich nakladek (po jednej na monitor)."""

    def __init__(self, color: str | QColor = "#E53935", width: int = 4, font_size: int = DEFAULT_FONT_SIZE,
                 jpeg_quality: int = 92, save_dir: str = ""):
        self.tool: str | None = None
        self.color = QColor(color)
        self.width = max(MIN_WIDTH, min(MAX_WIDTH, int(width)))
        self.font_size = max(FONT_SIZES[0], min(FONT_SIZES[-1], int(font_size)))
        self.jpeg_quality = max(1, min(100, int(jpeg_quality)))
        self.save_dir = save_dir                    # ostatnio uzyty katalog zapisu


@dataclass
class Item:
    kind: str                                   # jedno z TOOLS
    color: QColor
    width: int
    points: list[QPointF] = field(default_factory=list)   # pen: slad; line/arrow/rect: [start, koniec]; pointer: [czubek]; text: [lewy gorny rog]
    text: str = ""                                        # tylko text
    size: int = DEFAULT_FONT_SIZE                         # tylko text: wysokosc czcionki w pikselach


def constrain_axis(start: QPointF, end: QPointF) -> QPointF:
    """Shift przy linii/strzalce: linia pozioma albo pionowa (wg wiekszego przesuniecia)."""
    if abs(end.x() - start.x()) >= abs(end.y() - start.y()):
        return QPointF(end.x(), start.y())
    return QPointF(start.x(), end.y())


def constrain_square(start: QPointF, end: QPointF) -> QPointF:
    """Shift przy prostokacie: kwadrat."""
    side = max(abs(end.x() - start.x()), abs(end.y() - start.y()))
    return QPointF(start.x() + math.copysign(side, end.x() - start.x() or 1.0),
                   start.y() + math.copysign(side, end.y() - start.y() or 1.0))


def text_font(size: int) -> QFont:
    font = QFont(FONT_FAMILY)
    font.setPixelSize(int(size))
    return font


def text_rect(it: Item) -> QRectF:
    """Prostokat tekstu (lewy gorny rog = points[0]); ta sama miara w edytorze, podgladzie i wyniku."""
    fm = QFontMetricsF(text_font(it.size))
    lines = (it.text or " ").split("\n")
    width = max(fm.horizontalAdvance(line) for line in lines)
    return QRectF(it.points[0].x(), it.points[0].y(), width, fm.lineSpacing() * len(lines))


def pointer_size(width: int) -> float:
    return 16.0 + 4.0 * width


def arrow_geometry(a: QPointF, b: QPointF, width: float) -> tuple[QPointF, QPolygonF] | None:
    """(koniec trzonu, grot) strzalki od a do b; None dla zerowej dlugosci."""
    dx, dy = b.x() - a.x(), b.y() - a.y()
    length = math.hypot(dx, dy)
    if length < 1e-6:
        return None
    ux, uy = dx / length, dy / length
    head = min(max(12.0, width * 4.0), length)
    half = head * 0.42
    base = QPointF(b.x() - ux * head, b.y() - uy * head)
    nx, ny = -uy, ux
    poly = QPolygonF([b, QPointF(base.x() + nx * half, base.y() + ny * half),
                      QPointF(base.x() - nx * half, base.y() - ny * half)])
    # trzon konczy sie w polowie grotu, gdzie grot jest jeszcze szerszy od linii
    shaft_end = QPointF(base.x() + ux * head * 0.5, base.y() + uy * head * 0.5)
    return shaft_end, poly


def pointer_polygon(tip: QPointF, width: int) -> tuple[QPolygonF, float]:
    scale = pointer_size(width) / POINTER_HEIGHT
    return QPolygonF([QPointF(tip.x() + x * scale, tip.y() + y * scale) for x, y in POINTER_SHAPE]), scale


def _smooth_path(pts: list[QPointF]) -> QPainterPath:
    path = QPainterPath(pts[0])
    if len(pts) == 2:
        path.lineTo(pts[1])
        return path
    for i in range(1, len(pts) - 1):
        mid = QPointF((pts[i].x() + pts[i + 1].x()) / 2, (pts[i].y() + pts[i + 1].y()) / 2)
        path.quadTo(pts[i], mid)
    path.lineTo(pts[-1])
    return path


def paint_item(p: QPainter, it: Item) -> None:
    pts = it.points
    if not pts:
        return
    p.save()
    p.setRenderHint(QPainter.Antialiasing, True)
    pen = QPen(it.color, it.width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    if it.kind == "pen":
        if len(pts) == 1 or all(q == pts[0] for q in pts):
            p.setPen(Qt.NoPen)
            p.setBrush(it.color)
            p.drawEllipse(pts[0], it.width / 2.0, it.width / 2.0)
        else:
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawPath(_smooth_path(pts))
    elif it.kind == "line" and len(pts) >= 2:
        p.setPen(pen)
        p.drawLine(pts[0], pts[1])
    elif it.kind == "arrow" and len(pts) >= 2:
        geo = arrow_geometry(pts[0], pts[1], it.width)
        if geo:
            shaft_end, head = geo
            pen.setCapStyle(Qt.FlatCap)
            p.setPen(pen)
            p.drawLine(pts[0], shaft_end)
            p.setPen(Qt.NoPen)
            p.setBrush(it.color)
            p.drawPolygon(head)
    elif it.kind == "rect" and len(pts) >= 2:
        pen.setJoinStyle(Qt.MiterJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(pts[0], pts[1]).normalized())
    elif it.kind == "text" and it.text.strip():
        p.setRenderHint(QPainter.TextAntialiasing, True)
        p.setFont(text_font(it.size))
        p.setPen(it.color)
        p.drawText(text_rect(it), Qt.AlignLeft | Qt.AlignTop | Qt.TextDontClip, it.text)
    elif it.kind == "pointer":
        poly, scale = pointer_polygon(pts[0], it.width)
        # kursor myszy zawsze jest bialy z cienka czarna obwodka, niezaleznie od wybranego koloru
        p.setPen(QPen(QColor("#000000"), max(0.7, scale * 0.45), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(QColor("#FFFFFF"))
        p.drawPolygon(poly)
    p.restore()


def is_degenerate(it: Item) -> bool:
    """Linia/strzalka/prostokat bez dlugosci nie sa zapisywane."""
    if it.kind == "text":
        return not it.text.strip()
    if it.kind in ("line", "arrow", "rect"):
        return len(it.points) < 2 or it.points[0] == it.points[1]
    return not it.points


def save_jpeg(img: QImage, path: str, quality: int) -> str:
    """Zapisuje obraz jako JPG i zwraca faktyczna sciezke (dopisuje .jpg, gdy brak rozszerzenia). Rzuca OSError."""
    if not path.lower().endswith((".jpg", ".jpeg")):
        path += ".jpg"
    if not img.save(path, "JPG", max(1, min(100, int(quality)))):
        raise OSError(f"cannot write {path}")
    return path


def render_result(shot: QImage, sel: QRect, view_size: QSize, items: list[Item]) -> QImage:
    """Wycina zaznaczenie ze zrzutu (piksele fizyczne) i rysuje na nim adnotacje zapisane we wspolrzednych okna."""
    fx = shot.width() / max(1, view_size.width())
    fy = shot.height() / max(1, view_size.height())
    src = QRect(round(sel.x() * fx), round(sel.y() * fy), max(1, round(sel.width() * fx)),
                max(1, round(sel.height() * fy))).intersected(shot.rect())
    img = shot.copy(src).convertToFormat(QImage.Format_RGB32)
    p = QPainter(img)
    p.translate(-src.x(), -src.y())
    p.scale(fx, fy)
    for it in items:
        paint_item(p, it)
    p.end()
    return img
