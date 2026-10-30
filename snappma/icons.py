"""Ikony rysowane w kodzie (bez plikow): narzedzia paska i ikona programu."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QIcon, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
                           QPolygonF)

from .annotations import POINTER_HEIGHT, POINTER_SHAPE, arrow_geometry

LIGHT = QColor("#F2F2F2")
YELLOW = QColor("#FFD60A")      # ikony pedzla, linii, strzalki i prostokata
GRID = 24.0          # ikony sa rysowane na siatce 24x24


def _canvas(size: int, ratio: int = 2) -> tuple[QPixmap, QPainter]:
    pm = QPixmap(size * ratio, size * ratio)
    pm.setDevicePixelRatio(ratio)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.scale(size / GRID, size / GRID)
    return pm, p


def tool_icon(name: str, size: int = 24) -> QIcon:
    pm, p = _canvas(size)
    pen = QPen(YELLOW, 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    if name == "pen":
        path = QPainterPath(QPointF(4, 17))
        path.cubicTo(7, 5, 10, 5, 12, 12)
        path.cubicTo(14, 19, 17, 19, 20, 7)
        p.drawPath(path)
    elif name == "line":
        p.drawLine(QPointF(5, 19), QPointF(19, 5))
    elif name == "arrow":
        geo = arrow_geometry(QPointF(4.5, 19.5), QPointF(19.5, 4.5), 1.6)
        pen.setCapStyle(Qt.FlatCap)
        p.setPen(pen)
        p.drawLine(QPointF(4.5, 19.5), geo[0])
        p.setPen(Qt.NoPen)
        p.setBrush(YELLOW)
        p.drawPolygon(geo[1])
    elif name == "rect":
        pen.setJoinStyle(Qt.MiterJoin)
        p.setPen(pen)
        p.drawRect(QRectF(4, 6, 16, 12))
    elif name == "text":
        p.drawLine(QPointF(6, 6.5), QPointF(18, 6.5))
        p.drawLine(QPointF(12, 6.5), QPointF(12, 19))
        p.drawLine(QPointF(9.5, 19), QPointF(14.5, 19))
    elif name == "pointer":
        s = 19.0 / POINTER_HEIGHT
        poly = QPolygonF([QPointF(6 + x * s, 2.5 + y * s) for x, y in POINTER_SHAPE])
        p.setPen(QPen(QColor("#000000"), 0.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(QColor("#FFFFFF"))
        p.drawPolygon(poly)
    elif name == "undo":
        pen.setColor(LIGHT)
        p.setPen(pen)
        path = QPainterPath(QPointF(18.5, 18))
        path.cubicTo(19, 11, 14, 8.5, 8.5, 10)
        p.drawPath(path)
        p.drawPolyline(QPolygonF([QPointF(11.5, 5.5), QPointF(7, 10.2), QPointF(11.8, 14.2)]))
    elif name == "save":
        pen.setColor(LIGHT)
        pen.setWidthF(1.8)
        p.setPen(pen)
        p.drawPolygon(QPolygonF([QPointF(5, 4.5), QPointF(16, 4.5), QPointF(19.5, 8), QPointF(19.5, 19.5),
                                 QPointF(5, 19.5)]))
        p.drawRect(QRectF(8.5, 4.5, 6.5, 4.5))
        p.drawRect(QRectF(8, 13, 8, 6.5))
    elif name == "copy":
        p.setPen(QPen(QColor("#5CD65C"), 2.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPolyline(QPolygonF([QPointF(4.5, 12.5), QPointF(9.8, 17.8), QPointF(19.5, 6.5)]))
    elif name == "cancel":
        p.setPen(QPen(QColor("#FF6B6B"), 2.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawLine(QPointF(6, 6), QPointF(18, 18))
        p.drawLine(QPointF(18, 6), QPointF(6, 18))
    p.end()
    return QIcon(pm)


def app_image(size: int = 256) -> QImage:
    """Ikona programu: niebieski kwadrat, biala ramka zaznaczenia i czerwona strzalka."""
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.scale(size / 100.0, size / 100.0)
    grad = QLinearGradient(0, 0, 100, 100)
    grad.setColorAt(0, QColor("#3B9BFF"))
    grad.setColorAt(1, QColor("#1747B8"))
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(grad))
    p.drawRoundedRect(QRectF(4, 4, 92, 92), 20, 20)
    frame = QPen(QColor("#FFFFFF"), 5.5, Qt.SolidLine, Qt.FlatCap, Qt.MiterJoin)
    p.setPen(frame)
    p.setBrush(Qt.NoBrush)
    for (cx, cy, dx, dy) in ((22, 22, 1, 1), (78, 22, -1, 1), (22, 78, 1, -1), (78, 78, -1, -1)):
        path = QPainterPath(QPointF(cx + dx * 17, cy))
        path.lineTo(cx, cy)
        path.lineTo(cx, cy + dy * 17)
        p.drawPath(path)
    geo = arrow_geometry(QPointF(34, 66), QPointF(68, 32), 5.5)
    p.setPen(QPen(QColor("#FF4D4D"), 9, Qt.SolidLine, Qt.FlatCap))
    p.drawLine(QPointF(34, 66), geo[0])
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#FF4D4D"))
    p.drawPolygon(geo[1])
    p.end()
    return img


def app_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(QPixmap.fromImage(app_image(size)))
    return icon
