"""Helpers for the cinematic background and smooth animations."""
from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    Qt,
)
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPixmap, QRadialGradient
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QWidget


class CinemaBackground(QWidget):
    """Quiet, deep, slightly-warm cinematic backdrop.

    Static (no animation) so it never competes with content. Two radial
    glows in the corners give depth, the rest is near-black like the
    Apple TV home screen.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._backdrop: QPixmap | None = None

    def set_backdrop(self, pix: QPixmap | None) -> None:
        """Optional full-bleed image painted behind the gradients (hero)."""
        self._backdrop = pix
        self.update()

    def paintEvent(self, _evt) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        # Base black
        p.fillRect(self.rect(), QColor("#000000"))

        if self._backdrop and not self._backdrop.isNull():
            scaled = self._backdrop.scaled(
                w, h,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (scaled.width() - w) // -2
            y = (scaled.height() - h) // -2
            p.setOpacity(0.55)
            p.drawPixmap(x, y, scaled)
            p.setOpacity(1.0)
            # darken bottom for legibility
            grad = QLinearGradient(0, 0, 0, h)
            grad.setColorAt(0.0, QColor(0, 0, 0, 80))
            grad.setColorAt(0.55, QColor(0, 0, 0, 200))
            grad.setColorAt(1.0, QColor(0, 0, 0, 255))
            p.fillRect(self.rect(), grad)

        # subtle warm glow top-left
        g1 = QRadialGradient(QPointF(w * 0.1, h * 0.0), max(w, h) * 0.6)
        g1.setColorAt(0.0, QColor(244, 117, 33, 38))
        g1.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillRect(self.rect(), g1)

        # cool glow bottom-right
        g2 = QRadialGradient(QPointF(w * 1.0, h * 1.0), max(w, h) * 0.5)
        g2.setColorAt(0.0, QColor(90, 100, 250, 30))
        g2.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillRect(self.rect(), g2)


# ─── helpers ────────────────────────────────────────────────────────────────


def fade_in(widget: QWidget, *, duration: int = 280) -> QPropertyAnimation:
    """Animate ``widget`` from opacity 0 → 1. Returns the animation so the
    caller can chain or keep a reference."""
    eff = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(eff)
    eff.setOpacity(0.0)
    anim = QPropertyAnimation(eff, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    return anim


def apply_shadow(
    widget: QWidget,
    *,
    blur: int = 30,
    y_offset: int = 8,
    x_offset: int = 0,
    alpha: int = 120,
) -> QGraphicsDropShadowEffect:
    """Attach a soft drop shadow effect to ``widget`` (kept for compat)."""
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setOffset(x_offset, y_offset)
    eff.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(eff)
    return eff
