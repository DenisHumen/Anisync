"""Home — hero, continue watching, providers grid."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from anisync.core.library import get_library
from anisync.core.models import HistoryEntry
from anisync.core.registry import provider_registry
from anisync.ui.widgets.anime_card import AnimeCard


class HomePage(QWidget):
    open_details = Signal(object)  # AnimeSummary
    request_search = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 24, 32, 24)
        root.setSpacing(24)

        # Hero
        hero = QFrame()
        hero.setObjectName("card")
        hero.setMinimumHeight(220)
        h = QVBoxLayout(hero)
        h.setContentsMargins(32, 32, 32, 32)
        h.setSpacing(8)
        title = QLabel("Anisync")
        title.setObjectName("h1")
        subtitle = QLabel("Discover, stream and download anime — all in one place.")
        subtitle.setObjectName("muted")
        h.addWidget(title)
        h.addWidget(subtitle)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        explore = QPushButton("Explore catalog")
        explore.setProperty("accent", True)
        explore.clicked.connect(lambda: self.request_search.emit(""))
        btn_row.addWidget(explore)
        btn_row.addStretch(1)
        h.addLayout(btn_row)
        root.addWidget(hero)

        # Providers
        prov_label = QLabel("Sources")
        prov_label.setObjectName("h2")
        root.addWidget(prov_label)

        prow = QHBoxLayout()
        prow.setSpacing(12)
        for p in provider_registry.values():
            chip = QPushButton(p.display_name)
            chip.setProperty("accent", True)
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.clicked.connect(lambda _=False, name=p.display_name: self.request_search.emit(""))
            prow.addWidget(chip)
        prow.addStretch(1)
        root.addLayout(prow)

        # Continue watching
        cw_label = QLabel("Continue watching")
        cw_label.setObjectName("h2")
        root.addWidget(cw_label)

        self._continue_area = QScrollArea()
        self._continue_area.setWidgetResizable(True)
        self._continue_area.setFrameShape(QFrame.Shape.NoFrame)
        self._continue_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._continue_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        root.addWidget(self._continue_area)
        root.addStretch(1)

        self.refresh()

    def refresh(self) -> None:
        lib = get_library()
        history: list[HistoryEntry] = lib.list_history(limit=15)
        container = QWidget()
        h = QHBoxLayout(container)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(12)
        if not history:
            empty = QLabel("Nothing watched yet — search for something to begin.")
            empty.setObjectName("muted")
            h.addWidget(empty)
        else:
            for entry in history:
                from anisync.core.models import AnimeSummary
                summary = AnimeSummary(
                    provider_id=entry.provider_id,
                    url=entry.anime_url,
                    title=entry.title or entry.anime_url,
                    poster_url=entry.poster_url,
                )
                card = AnimeCard(summary, on_click=self.open_details.emit)
                h.addWidget(card)
        h.addStretch(1)
        self._continue_area.setWidget(container)
        container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
