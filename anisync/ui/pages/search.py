"""Search page — Apple-TV / Crunchyroll style.

Big single-line search field at the top with a thin underline. As the
user types, results appear below in a responsive **grid of poster
cards** (not table rows). Provider filter is a horizontal chip strip.
"""
from __future__ import annotations

import asyncio

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
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
from anisync.ui.widgets.anime_card import POSTER_W, PosterCard
from anisync.ui.widgets.spinner import Spinner
from anisync.utils.async_runner import run_async


# Card footprint incl. the padding PosterCard reserves for its hover scale.
_CARD_W = POSTER_W + 24
# Horizontal page padding (body contentsMargins left+right).
_PAGE_PAD = 128


class SearchPage(QWidget):
    open_details = Signal(object)
    error = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._cards: list[PosterCard] = []
        self._cols = 6
        # Monotonic token: a response is applied only if it belongs to the
        # latest query, so a slow old request can't overwrite fresh results.
        self._req_seq = 0

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        outer.addWidget(scroll)

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        v = QVBoxLayout(body)
        v.setContentsMargins(64, 40, 64, 60)
        v.setSpacing(20)
        scroll.setWidget(body)

        # ── search field row ─────────────────────────────────────────
        kicker = QLabel("SEARCH")
        kicker.setObjectName("kicker")
        v.addWidget(kicker)

        bar = QHBoxLayout()
        bar.setSpacing(16)

        self._input = QLineEdit()
        self._input.setObjectName("searchBig")
        self._input.setPlaceholderText("Search by title…")
        self._input.setMinimumHeight(56)
        self._input.textChanged.connect(self._on_text_changed)
        self._input.returnPressed.connect(self._do_search)
        bar.addWidget(self._input, 1)

        self._spinner = Spinner(22, "#F47521")
        bar.addWidget(self._spinner)
        v.addLayout(bar)

        # ── provider filter chips ────────────────────────────────────
        chip_row = QHBoxLayout()
        chip_row.setSpacing(8)
        self._provider_filter: str | None = None
        self._chip_group = QButtonGroup(self)
        self._chip_group.setExclusive(True)
        chips = [("All sources", None)] + [(p.display_name, p.id) for p in provider_registry.values()]
        for label, pid in chips:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setObjectName("outlined")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if pid is None:
                btn.setChecked(True)
            btn.clicked.connect(lambda _=False, p=pid: self._on_filter(p))
            self._chip_group.addButton(btn)
            chip_row.addWidget(btn)
        chip_row.addStretch(1)
        v.addLayout(chip_row)

        # ── status ──
        self._status = QLabel("Start typing to discover anime…")
        self._status.setObjectName("muted")
        v.addWidget(self._status)

        # ── results grid ─────────────────────────────────────────────
        self._grid_wrap = QWidget()
        self._grid_wrap.setStyleSheet("background: transparent;")
        self._grid = QGridLayout(self._grid_wrap)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(0)
        self._grid.setVerticalSpacing(8)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        v.addWidget(self._grid_wrap)
        v.addStretch(1)

        # debounce
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(320)
        self._debounce.timeout.connect(self._do_search)

    # ── public ────────────────────────────────────────────────────────────

    def set_query(self, q: str) -> None:
        self._input.setText(q)
        if q:
            self._do_search()

    def focus_input(self) -> None:
        self._input.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self._input.selectAll()

    # ── input ─────────────────────────────────────────────────────────────

    def _on_text_changed(self, _txt: str) -> None:
        if len(self._input.text().strip()) >= 2:
            self._debounce.start()
        elif not self._input.text().strip():
            self._clear_results()
            self._status.setText("Start typing to discover anime…")

    def _on_filter(self, provider_id: str | None) -> None:
        self._provider_filter = provider_id
        if self._input.text().strip():
            self._do_search()

    # ── search ────────────────────────────────────────────────────────────

    def _do_search(self) -> None:
        q = self._input.text().strip()
        if not q:
            return
        self._req_seq += 1
        seq = self._req_seq
        self._clear_results()
        self._spinner.start()
        self._status.setText(f"Searching for “{q}”…")
        run_async(
            self._run(q),
            on_done=lambda items, s=seq: self._render(items, s),
            on_error=lambda e, s=seq: self._on_err(e, s),
        )

    async def _run(self, query: str) -> list[AnimeSummary]:
        providers = (
            [provider_registry[self._provider_filter]] if self._provider_filter
            else list(provider_registry.values())
        )
        gathered = await asyncio.gather(
            *(p.search(query, limit=30) for p in providers),
            return_exceptions=True,
        )
        merged: list[AnimeSummary] = []
        for r in gathered:
            if isinstance(r, list):
                merged.extend(r)
        # dedupe
        seen = set()
        out = []
        for s in merged:
            k = (s.provider_id, s.url)
            if k in seen:
                continue
            seen.add(k)
            out.append(s)
        return out

    def _render(self, items: list[AnimeSummary], seq: int) -> None:
        if seq != self._req_seq:
            return  # stale response from a superseded query
        self._spinner.stop()
        self._clear_results()
        if not items:
            self._status.setText("No matches.")
            return
        self._status.setText(f"{len(items)} result(s)")
        self._cards = [
            PosterCard(s, on_click=self.open_details.emit) for s in items
        ]
        self._cols = self._column_count()
        self._layout_cards()

    def _on_err(self, exc: Exception, seq: int) -> None:
        if seq != self._req_seq:
            return
        self._spinner.stop()
        self._status.setText("Search failed.")
        self.error.emit(str(exc))

    def _clear_results(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._cards = []

    # ── responsive grid ─────────────────────────────────────────────────────

    def _column_count(self) -> int:
        # Reserve a little for the vertical scrollbar; grid spacing is 0 here.
        avail = self.width() - _PAGE_PAD - 16
        return max(1, avail // _CARD_W)

    def _layout_cards(self) -> None:
        # Re-place the already-built cards (no re-fetch) at the current
        # column count so the grid reflows with the window width.
        for card in self._cards:
            self._grid.removeWidget(card)
        for idx, card in enumerate(self._cards):
            self._grid.addWidget(card, idx // self._cols, idx % self._cols)

    def resizeEvent(self, evt):  # noqa: N802
        super().resizeEvent(evt)
        if not self._cards:
            return
        cols = self._column_count()
        if cols != self._cols:
            self._cols = cols
            self._layout_cards()
