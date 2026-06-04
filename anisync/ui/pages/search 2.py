"""Cross-provider search page."""
from __future__ import annotations

import asyncio

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from anisync.core.models import AnimeSummary
from anisync.core.registry import provider_registry
from anisync.utils.async_runner import run_async
from anisync.ui.widgets.anime_card import AnimeCard


class SearchPage(QWidget):
    open_details = Signal(object)
    error = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 24, 32, 24)
        root.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel("Search")
        title.setObjectName("h1")
        header.addWidget(title)
        header.addStretch(1)
        root.addLayout(header)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        self._input = QLineEdit()
        self._input.setObjectName("search")
        self._input.setPlaceholderText("Search anime across providers…")
        self._input.returnPressed.connect(self._do_search)
        bar.addWidget(self._input, 1)

        self._provider_box = QComboBox()
        self._provider_box.addItem("All providers", userData=None)
        for p in provider_registry.values():
            self._provider_box.addItem(p.display_name, userData=p.id)
        bar.addWidget(self._provider_box)

        btn = QPushButton("Search")
        btn.setProperty("accent", True)
        btn.clicked.connect(self._do_search)
        bar.addWidget(btn)

        root.addLayout(bar)

        self._status = QLabel("Type a query and press Enter.")
        self._status.setObjectName("muted")
        root.addWidget(self._status)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        root.addWidget(self._scroll, 1)

        self._results_widget = QWidget()
        self._grid = QGridLayout(self._results_widget)
        self._grid.setSpacing(16)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._scroll.setWidget(self._results_widget)

    def set_query(self, query: str) -> None:
        self._input.setText(query)
        if query:
            self._do_search()

    def _do_search(self) -> None:
        query = self._input.text().strip()
        if not query:
            self._status.setText("Please enter a search query.")
            return
        self._clear_grid()
        self._status.setText(f"Searching for “{query}”…")

        selected = self._provider_box.currentData()
        providers = (
            [provider_registry[selected]] if selected else list(provider_registry.values())
        )
        run_async(
            self._run_search(providers, query),
            on_done=self._render,
            on_error=lambda e: (
                self._status.setText("Search failed."),
                self.error.emit(str(e)),
            ),
        )

    async def _run_search(self, providers, query):
        results: list[AnimeSummary] = []
        tasks = [p.search(query, limit=24) for p in providers]
        for r in await asyncio.gather(*tasks, return_exceptions=True):
            if isinstance(r, list):
                results.extend(r)
        return results

    def _render(self, results: list[AnimeSummary]) -> None:
        self._clear_grid()
        if not results:
            self._status.setText("No results.")
            return
        self._status.setText(f"{len(results)} result(s).")
        cols = 6
        for i, s in enumerate(results):
            card = AnimeCard(s, on_click=self.open_details.emit)
            self._grid.addWidget(card, i // cols, i % cols)

    def _clear_grid(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
