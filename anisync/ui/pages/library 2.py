"""Library: favorites + custom lists."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from anisync.core.library import get_library
from anisync.core.models import ListKind
from anisync.ui.widgets.anime_card import AnimeCard


_KIND_LABELS = [
    ("Favorites", ListKind.FAVORITE),
    ("Watching", ListKind.WATCHING),
    ("Planning", ListKind.PLANNING),
    ("Completed", ListKind.COMPLETED),
    ("Dropped", ListKind.DROPPED),
]


class LibraryPage(QWidget):
    open_details = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 24, 32, 24)
        root.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel("My Library")
        title.setObjectName("h1")
        header.addWidget(title)
        header.addStretch(1)
        self._kind_box = QComboBox()
        for label, kind in _KIND_LABELS:
            self._kind_box.addItem(label, userData=kind)
        self._kind_box.currentIndexChanged.connect(self.refresh)
        header.addWidget(self._kind_box)
        root.addLayout(header)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        root.addWidget(self._scroll, 1)

    def refresh(self) -> None:
        kind = self._kind_box.currentData() or ListKind.FAVORITE
        items = get_library().list_anime(kind)
        container = QWidget()
        if not items:
            v = QVBoxLayout(container)
            empty = QLabel("Nothing here yet.")
            empty.setObjectName("muted")
            empty.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            v.addWidget(empty)
            v.addStretch(1)
        else:
            grid = QGridLayout(container)
            grid.setSpacing(16)
            grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            cols = 6
            for i, s in enumerate(items):
                card = AnimeCard(s, on_click=self.open_details.emit)
                grid.addWidget(card, i // cols, i % cols)
        self._scroll.setWidget(container)
