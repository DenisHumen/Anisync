"""Clickable anime card with poster + title + meta."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
)

from anisync.core.models import AnimeSummary
from anisync.ui.widgets.poster_loader import PosterLoader


class AnimeCard(QFrame):
    clicked = Signal(object)  # AnimeSummary

    def __init__(self, summary: AnimeSummary, *, on_click: Callable[[AnimeSummary], None] | None = None):
        super().__init__()
        self.summary = summary
        self.setObjectName("card")
        self.setFixedWidth(180)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        v = QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 10)
        v.setSpacing(6)

        self._poster = QLabel()
        self._poster.setFixedSize(164, 232)
        self._poster.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._poster.setStyleSheet("background:#000; border-radius:8px;")
        self._poster.setText("…")
        v.addWidget(self._poster)

        title = QLabel(summary.title)
        title.setObjectName("cardTitle")
        title.setWordWrap(True)
        title.setMaximumHeight(40)
        v.addWidget(title)

        meta_parts: list[str] = []
        if summary.year:
            meta_parts.append(str(summary.year))
        if summary.type:
            meta_parts.append(summary.type)
        if summary.episodes_count:
            meta_parts.append(f"{summary.episodes_count} ep")
        if meta_parts:
            meta = QLabel(" · ".join(meta_parts))
            meta.setObjectName("cardMeta")
            v.addWidget(meta)

        self._loader = PosterLoader(summary.poster_url)
        self._loader.loaded.connect(self._set_pixmap)
        self._loader.start()

        if on_click:
            self.clicked.connect(on_click)

    def _set_pixmap(self, data: bytes) -> None:
        if not data:
            return
        pix = QPixmap()
        if pix.loadFromData(data):
            self._poster.setPixmap(
                pix.scaled(
                    self._poster.size(),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.summary)
        super().mousePressEvent(event)
