"""Animated circular spinner using QPainter (no QtSvg dependency)."""
from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget


class Spinner(QWidget):
    def __init__(self, size: int = 18, color: str = "#FFFFFF") -> None:
        super().__init__()
        self.setFixedSize(size, size)
        self._angle = 0
        self._color = QColor(color)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step)

    def start(self) -> None:
        if not self._timer.isActive():
            self._timer.start(45)

    def stop(self) -> None:
        self._timer.stop()
        self.update()

    def _step(self) -> None:
        self._angle = (self._angle + 22) % 360
        self.update()

    def paintEvent(self, _evt) -> None:  # noqa: N802
        if not self._timer.isActive():
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(2, 2, -2, -2)
        pen = QPen(self._color, 2.2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        # 270° arc rotating
        p.drawArc(rect, -self._angle * 16, 270 * 16)
