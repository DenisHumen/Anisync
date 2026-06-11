"""Crisp QPainter-drawn monochrome icons.

Media-control glyphs (⏮ ❚❚ ⟲ ⤢ 🔊 …) are not reliably present in the
default fonts on Linux (DejaVu renders them as tofu boxes) and the
colour-emoji fallbacks clash with the monochrome control bar elsewhere.
Drawing the handful of icons we need keeps the UI identical on Windows,
macOS and Linux.

Icons are rendered at 4× and downscaled so they stay sharp on HiDPI
screens — the same approach as the search icon in ``topnav``.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
)

_SCALE = 4


def _begin(px: int) -> tuple[QPixmap, QPainter, float]:
    s = px * _SCALE
    pm = QPixmap(s, s)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    return pm, p, float(s)


def _end(pm: QPixmap, p: QPainter, px: int) -> QPixmap:
    p.end()
    return pm.scaled(
        px, px,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def _pen(color: str, s: float, w: float = 0.09) -> QPen:
    pen = QPen(QColor(color))
    pen.setWidthF(s * w)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


# ─── media controls ─────────────────────────────────────────────────────────


def play_icon(color: str = "#FFFFFF", px: int = 18) -> QIcon:
    pm, p, s = _begin(px)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    p.drawPolygon(QPolygonF([
        QPointF(s * 0.34, s * 0.20),
        QPointF(s * 0.34, s * 0.80),
        QPointF(s * 0.84, s * 0.50),
    ]))
    return QIcon(_end(pm, p, px))


def pause_icon(color: str = "#FFFFFF", px: int = 18) -> QIcon:
    pm, p, s = _begin(px)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    r = s * 0.05
    p.drawRoundedRect(QRectF(s * 0.28, s * 0.22, s * 0.15, s * 0.56), r, r)
    p.drawRoundedRect(QRectF(s * 0.57, s * 0.22, s * 0.15, s * 0.56), r, r)
    return QIcon(_end(pm, p, px))


def prev_icon(color: str = "#FFFFFF", px: int = 18) -> QIcon:
    pm, p, s = _begin(px)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    p.drawRoundedRect(QRectF(s * 0.20, s * 0.22, s * 0.12, s * 0.56), s * 0.04, s * 0.04)
    p.drawPolygon(QPolygonF([
        QPointF(s * 0.80, s * 0.22),
        QPointF(s * 0.80, s * 0.78),
        QPointF(s * 0.38, s * 0.50),
    ]))
    return QIcon(_end(pm, p, px))


def next_icon(color: str = "#FFFFFF", px: int = 18) -> QIcon:
    pm, p, s = _begin(px)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    p.drawPolygon(QPolygonF([
        QPointF(s * 0.20, s * 0.22),
        QPointF(s * 0.20, s * 0.78),
        QPointF(s * 0.62, s * 0.50),
    ]))
    p.drawRoundedRect(QRectF(s * 0.68, s * 0.22, s * 0.12, s * 0.56), s * 0.04, s * 0.04)
    return QIcon(_end(pm, p, px))


def skip_icon(seconds: int = 10, *, forward: bool = True,
              color: str = "#FFFFFF", px: int = 22) -> QIcon:
    """Circular arrow with the seconds count inside (Plex/YouTube style)."""
    pm, p, s = _begin(px)
    p.setPen(_pen(color, s, 0.07))
    p.setBrush(Qt.BrushStyle.NoBrush)
    r = s * 0.34
    cx, cy = s * 0.5, s * 0.54
    rect = QRectF(cx - r, cy - r, 2 * r, 2 * r)
    # Arc leaves a gap next to 12 o'clock; the head sits at the top and
    # points in the direction of travel.
    if forward:
        p.drawArc(rect, 90 * 16, -300 * 16)
    else:
        p.drawArc(rect, 90 * 16, 300 * 16)
    top_y = cy - r
    head_dx = s * 0.17 if forward else -s * 0.17
    base_dx = -s * 0.03 if forward else s * 0.03
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    p.drawPolygon(QPolygonF([
        QPointF(cx + head_dx, top_y),
        QPointF(cx + base_dx, top_y - s * 0.11),
        QPointF(cx + base_dx, top_y + s * 0.11),
    ]))
    f = QFont()
    f.setPixelSize(int(s * 0.32))
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor(color))
    p.drawText(QRectF(0, cy - r, s, 2 * r), Qt.AlignmentFlag.AlignCenter, str(seconds))
    return QIcon(_end(pm, p, px))


def back_icon(color: str = "#FFFFFF", px: int = 18) -> QIcon:
    pm, p, s = _begin(px)
    p.setPen(_pen(color, s))
    p.drawLine(QPointF(s * 0.78, s * 0.50), QPointF(s * 0.26, s * 0.50))
    p.drawLine(QPointF(s * 0.26, s * 0.50), QPointF(s * 0.48, s * 0.28))
    p.drawLine(QPointF(s * 0.26, s * 0.50), QPointF(s * 0.48, s * 0.72))
    return QIcon(_end(pm, p, px))


def fullscreen_icon(color: str = "#FFFFFF", px: int = 18) -> QIcon:
    pm, p, s = _begin(px)
    p.setPen(_pen(color, s, 0.08))
    m, k = s * 0.20, s * 0.20
    # four expand corners
    p.drawPolyline(QPolygonF([QPointF(m, m + k), QPointF(m, m), QPointF(m + k, m)]))
    p.drawPolyline(QPolygonF([QPointF(s - m - k, m), QPointF(s - m, m), QPointF(s - m, m + k)]))
    p.drawPolyline(QPolygonF([QPointF(s - m, s - m - k), QPointF(s - m, s - m), QPointF(s - m - k, s - m)]))
    p.drawPolyline(QPolygonF([QPointF(m + k, s - m), QPointF(m, s - m), QPointF(m, s - m - k)]))
    return QIcon(_end(pm, p, px))


def volume_pixmap(color: str = "#B4B4BE", px: int = 18) -> QPixmap:
    """Monochrome speaker glyph (used as a static QLabel pixmap)."""
    pm, p, s = _begin(px)
    col = QColor(color)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(col)
    p.drawPolygon(QPolygonF([
        QPointF(s * 0.10, s * 0.40), QPointF(s * 0.24, s * 0.40),
        QPointF(s * 0.44, s * 0.22), QPointF(s * 0.44, s * 0.78),
        QPointF(s * 0.24, s * 0.60), QPointF(s * 0.10, s * 0.60),
    ]))
    pen = _pen(color, s, 0.05)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawArc(QRectF(s * 0.31, s * 0.37, s * 0.26, s * 0.26), -50 * 16, 100 * 16)
    p.drawArc(QRectF(s * 0.24, s * 0.30, s * 0.40, s * 0.40), -50 * 16, 100 * 16)
    return _end(pm, p, px)


# ─── window controls (frameless Win/Linux title bar) ───────────────────────


def minimize_icon(color: str = "#FFFFFF", px: int = 14) -> QIcon:
    pm, p, s = _begin(px)
    p.setPen(_pen(color, s, 0.09))
    p.drawLine(QPointF(s * 0.22, s * 0.55), QPointF(s * 0.78, s * 0.55))
    return QIcon(_end(pm, p, px))


def maximize_icon(color: str = "#FFFFFF", px: int = 14) -> QIcon:
    pm, p, s = _begin(px)
    p.setPen(_pen(color, s, 0.09))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(QRectF(s * 0.24, s * 0.24, s * 0.52, s * 0.52), s * 0.05, s * 0.05)
    return QIcon(_end(pm, p, px))


def close_icon(color: str = "#FFFFFF", px: int = 14) -> QIcon:
    pm, p, s = _begin(px)
    p.setPen(_pen(color, s, 0.09))
    p.drawLine(QPointF(s * 0.26, s * 0.26), QPointF(s * 0.74, s * 0.74))
    p.drawLine(QPointF(s * 0.74, s * 0.26), QPointF(s * 0.26, s * 0.74))
    return QIcon(_end(pm, p, px))
