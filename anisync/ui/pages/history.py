"""Recently watched episodes (history view)."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from anisync.core.library import get_library
from anisync.core.models import AnimeSummary


class HistoryPage(QWidget):
    open_details = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(64, 32, 64, 32)
        root.setSpacing(16)

        kicker = QLabel("RECENTLY WATCHED")
        kicker.setObjectName("kicker")
        root.addWidget(kicker)

        title = QLabel("History")
        title.setObjectName("h1")
        root.addWidget(title)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        # QScrollArea autofills its viewport with the system palette —
        # without this the page shows a grey sheet over the dark theme.
        self._scroll.setStyleSheet("background: transparent;")
        root.addWidget(self._scroll, 1)

    def refresh(self) -> None:
        entries = get_library().list_history(limit=100)
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        v = QVBoxLayout(container)
        v.setSpacing(10)
        if not entries:
            empty = QLabel("Nothing watched yet.")
            empty.setObjectName("muted")
            v.addWidget(empty)
        else:
            for e in entries:
                row = QFrame()
                row.setObjectName("card")
                h = QVBoxLayout(row)
                h.setContentsMargins(14, 10, 14, 10)
                top = QHBoxLayout()
                lbl = QLabel(f"{e.title or e.anime_url} — Episode {e.episode_number}")
                lbl.setObjectName("cardTitle")
                top.addWidget(lbl)
                top.addStretch(1)
                meta = QLabel(e.watched_at.strftime("%Y-%m-%d %H:%M"))
                meta.setObjectName("cardMeta")
                top.addWidget(meta)
                h.addLayout(top)

                if e.duration_seconds:
                    pb = QProgressBar()
                    pb.setRange(0, 1000)
                    pb.setValue(int(e.progress * 1000))
                    h.addWidget(pb)

                row.setCursor(Qt.CursorShape.PointingHandCursor)
                summary = AnimeSummary(
                    provider_id=e.provider_id, url=e.anime_url,
                    title=e.title or e.anime_url, poster_url=e.poster_url,
                )
                row.mousePressEvent = lambda _evt, s=summary: self.open_details.emit(s)
                v.addWidget(row)
        v.addStretch(1)
        self._scroll.setWidget(container)
