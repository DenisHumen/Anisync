"""Animated circular spinner using QPainter (no QtSvg dependency)."""
from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class Spinner(QWidget):
    def __init__(
        self,
        size: int = 18,
        color: str = "#FFFFFF",
        *,
        thickness: float = 2.2,
        auto_start: bool = False,
    ) -> None:
        super().__init__()
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._angle = 0
        self._color = QColor(color)
        self._thickness = thickness
        self._running = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step)
        if auto_start:
            self.start()

    def start(self) -> None:
        self._running = True
        if not self._timer.isActive():
            self._timer.start(40)
        self.update()

    def stop(self) -> None:
        self._running = False
        self._timer.stop()
        self.update()

    def hideEvent(self, e):  # noqa: N802
        # Pause the animation while off-screen to save CPU; the running
        # intent is preserved so showEvent can resume it.
        self._timer.stop()
        super().hideEvent(e)

    def showEvent(self, e):  # noqa: N802
        # Resume only if we were actually meant to be spinning — never
        # auto-start, otherwise an idle inline spinner animates forever.
        if self._running and not self._timer.isActive():
            self._timer.start(40)
        super().showEvent(e)

    def _step(self) -> None:
        self._angle = (self._angle + 18) % 360
        self.update()

    def paintEvent(self, _evt) -> None:  # noqa: N802
        # An idle spinner is invisible — no static track/arc left behind.
        if not self._running:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        m = int(self._thickness) + 2
        rect = self.rect().adjusted(m, m, -m, -m)
        # faint track
        track = QColor(self._color)
        track.setAlpha(45)
        pen_t = QPen(track, self._thickness)
        pen_t.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen_t)
        p.drawArc(rect, 0, 360 * 16)
        # moving arc
        pen = QPen(self._color, self._thickness)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawArc(rect, -self._angle * 16, 110 * 16)


class LoadingPanel(QWidget):
    """Centred big spinner with a label — for full-page loading states."""

    def __init__(
        self,
        message: str = "Loading…",
        parent: QWidget | None = None,
        *,
        size: int = 52,
        color: str = "#F47521",   # brand accent — keep spinners on-palette
    ) -> None:
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(40, 80, 40, 80)
        v.setSpacing(18)
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._spinner = Spinner(size=size, color=color, thickness=4, auto_start=True)
        v.addWidget(self._spinner, 0, Qt.AlignmentFlag.AlignHCenter)
        self._label = QLabel(message)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setObjectName("muted")
        self._label.setStyleSheet("font-size:14px;")
        v.addWidget(self._label)

    def set_message(self, text: str) -> None:
        self._label.setText(text)

    def stop(self) -> None:
        self._spinner.stop()
