"""Library: favorites + custom lists with a friendly empty state."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
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
    request_search = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(64, 32, 64, 32)
        root.setSpacing(20)

        header = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        kicker = QLabel("YOUR COLLECTION")
        kicker.setObjectName("kicker")
        title_col.addWidget(kicker)
        title = QLabel("My Library")
        title.setObjectName("h1")
        title_col.addWidget(title)
        header.addLayout(title_col)
        header.addStretch(1)
        self._kind_box = QComboBox()
        self._kind_box.setMinimumWidth(180)
        for label, kind in _KIND_LABELS:
            self._kind_box.addItem(label, userData=kind)
        self._kind_box.currentIndexChanged.connect(self.refresh)
        header.addWidget(self._kind_box)
        root.addLayout(header)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet("background: transparent;")
        root.addWidget(self._scroll, 1)

    def refresh(self) -> None:
        kind_val = self._kind_box.currentData() or ListKind.FAVORITE
        kind = ListKind(kind_val) if isinstance(kind_val, str) and not isinstance(kind_val, ListKind) else kind_val
        items = get_library().list_anime(kind)

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        if not items:
            v = QVBoxLayout(container)
            v.setContentsMargins(0, 80, 0, 0)
            v.setAlignment(Qt.AlignmentFlag.AlignCenter)
            v.setSpacing(14)

            mark = QLabel("✦")
            mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
            mark.setStyleSheet("font-size:60px; color:#2A2A33;")
            v.addWidget(mark)

            head = QLabel(f"No {self._kind_box.currentText().lower()} yet")
            head.setObjectName("h2")
            head.setAlignment(Qt.AlignmentFlag.AlignCenter)
            v.addWidget(head)

            sub = QLabel(
                "Discover anime in Search and add titles to your library."
            )
            sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sub.setStyleSheet("color:#8A8A95; font-size:14px;")
            v.addWidget(sub)

            v.addSpacing(8)
            cta = QPushButton("Browse catalog")
            cta.setObjectName("primary")
            cta.setCursor(Qt.CursorShape.PointingHandCursor)
            cta.setFixedWidth(180)
            cta.clicked.connect(lambda: self.request_search.emit(""))
            v.addWidget(cta, 0, Qt.AlignmentFlag.AlignHCenter)
            v.addStretch(1)
        else:
            grid = QGridLayout(container)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setSpacing(8)
            grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            cols = 6
            for i, s in enumerate(items):
                card = AnimeCard(s, on_click=self.open_details.emit)
                grid.addWidget(card, i // cols, i % cols)
        self._scroll.setWidget(container)
