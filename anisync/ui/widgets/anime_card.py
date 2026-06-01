"""Apple-TV style poster card.

The card has **no background**: the poster itself *is* the card. On
hover the whole tile smoothly scales up by ~6 % and gains an accent
ring, exactly like Apple TV / Crunchyroll. The title sits below the
poster, fading out under it when scaled.
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QRect,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
)

from anisync.core.models import AnimeSummary
from anisync.ui.widgets.poster_loader import PosterLoader


# Standard poster aspect 2:3 (e.g. 168x252 / 200x300)
POSTER_W = 200
POSTER_H = 300
LABEL_H = 44


class PosterCard(QFrame):
    """Single poster tile used in carousels and search grid."""

    clicked = Signal(object)  # AnimeSummary

    def __init__(
        self,
        summary: AnimeSummary,
        *,
        on_click: Callable[[AnimeSummary], None] | None = None,
        size: tuple[int, int] = (POSTER_W, POSTER_H),
    ) -> None:
        super().__init__()
        self.summary = summary
        self._w, self._h = size

        self.setObjectName("poster")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        # leave some padding around so the scale-up animation has room
        self.setFixedSize(self._w + 24, self._h + LABEL_H + 24)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        v = QVBoxLayout(self)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(8)

        self._img = QLabel()
        self._img.setObjectName("posterImg")
        self._img.setFixedSize(self._w, self._h)
        self._img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Apple-TV-style placeholder gradient
        self._img.setStyleSheet(
            f"background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            f"stop:0 #1A1A22, stop:1 #0D0D12);"
            f"border-radius: 10px; color:#3A3A4A; font-size:32px; font-weight:300;"
        )
        self._img.setText(self._initials(summary.title))
        v.addWidget(self._img, 0, Qt.AlignmentFlag.AlignHCenter)

        self._title = QLabel(summary.title)
        self._title.setObjectName("cardTitle")
        self._title.setWordWrap(True)
        self._title.setMaximumWidth(self._w)
        self._title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        v.addWidget(self._title)

        # scale animation: animate the image label's geometry
        self._scale_anim: QPropertyAnimation | None = None

        # async poster — parent loader to the card so it dies with us
        self._loader = PosterLoader(summary.poster_url, parent=self)
        self._loader.loaded.connect(self._apply_pixmap)
        self._loader.start()

        if on_click:
            self.clicked.connect(on_click)

    # ── visuals ────────────────────────────────────────────────────────────

    @staticmethod
    def _initials(title: str) -> str:
        parts = [w for w in title.split() if w]
        if not parts:
            return "?"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[1][0]).upper()

    def _apply_pixmap(self, data: bytes) -> None:
        if not data:
            return
        pix = QPixmap()
        if not pix.loadFromData(data):
            return
        scaled = pix.scaled(
            QSize(self._w, self._h),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        # The card may have been destroyed between fetch start and
        # completion (search grid cleared, page rebuilt, …).
        try:
            self._img.setText("")
            self._img.setPixmap(scaled)
        except RuntimeError:
            pass

    # ── hover scale ────────────────────────────────────────────────────────

    def enterEvent(self, e):  # noqa: N802
        self._animate_scale(1.07)
        self.setProperty("hovered", True)
        self._img.style().unpolish(self._img); self._img.style().polish(self._img)
        super().enterEvent(e)

    def leaveEvent(self, e):  # noqa: N802
        self._animate_scale(1.0)
        self.setProperty("hovered", False)
        self._img.style().unpolish(self._img); self._img.style().polish(self._img)
        super().leaveEvent(e)

    def _animate_scale(self, factor: float) -> None:
        target_w = int(self._w * factor)
        target_h = int(self._h * factor)
        # center within the card
        x = (self.width() - target_w) // 2
        y = 12 - int((target_h - self._h) / 2)
        end = QRect(x, y, target_w, target_h)
        # Stop & forget the previous animation safely. We do NOT use
        # DeleteWhenStopped — the underlying C++ object would be destroyed
        # while ``self._scale_anim`` still held a dangling shiboken wrapper,
        # producing “Internal C++ object already deleted” errors on the
        # next hover. Instead we parent to ``self`` and explicitly
        # ``deleteLater()`` the stale one.
        prev = self._scale_anim
        self._scale_anim = None
        if prev is not None:
            try:
                prev.stop()
                prev.deleteLater()
            except RuntimeError:
                pass
        anim = QPropertyAnimation(self._img, b"geometry", self)
        anim.setDuration(180)
        anim.setStartValue(self._img.geometry())
        anim.setEndValue(end)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.finished.connect(self._on_scale_finished)
        self._scale_anim = anim
        anim.start()

    def _on_scale_finished(self) -> None:
        self._scale_anim = None

    def mousePressEvent(self, e):  # noqa: N802
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.summary)
        super().mousePressEvent(e)


# Backwards-compatible alias — older modules still import AnimeCard
AnimeCard = PosterCard
