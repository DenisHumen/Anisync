"""Home page — Apple-TV-style hero + multiple horizontal carousels.

Layout:

* Full-width **hero** at the top: large title / synopsis / Play+Info,
  backdrop image bleeds behind, fades into the page.
* "Continue Watching" carousel populated from local history.
* "Trending Now" carousel populated by querying each provider's
  catalogue (we use a generic neutral search like "" / popular keyword).
"""
from __future__ import annotations

import asyncio
import random
import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from anisync.core.library import get_library
from anisync.core.models import AnimeSummary
from anisync.core.registry import provider_registry
from anisync.ui.glass import fade_in
from anisync.ui.widgets.carousel import Carousel
from anisync.ui.widgets.icons import play_icon
from anisync.ui.widgets.poster_loader import PosterLoader
from anisync.utils.async_runner import run_async


# Seeds used to populate the trending row when the catalogue has no
# dedicated "trending" endpoint. Picked to be safe / well-known so even
# small providers usually return matches.
TRENDING_SEEDS = ("naruto", "attack", "demon", "one piece", "jujutsu", "spy")

# How long fetched remote rows stay fresh. Re-querying every provider on
# every visit to Home wastes bandwidth and makes the hero re-randomize
# (visible content churn) each time the user passes through the page.
_REMOTE_TTL_SECONDS = 600


class HomePage(QWidget):
    open_details = Signal(object)
    play_featured = Signal(object)   # AnimeSummary — open details + autoplay
    request_search = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self._last_remote_refresh = float("-inf")   # → first refresh always fetches

        # ── scroll-able body ─────────────────────────────────────────
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
        v.setContentsMargins(0, 0, 0, 60)
        v.setSpacing(40)
        scroll.setWidget(body)

        # ── hero ─────────────────────────────────────────────────────
        self._hero = _Hero()
        self._hero.explore_clicked.connect(lambda: self.request_search.emit(""))
        self._hero.info_clicked.connect(self.open_details.emit)
        self._hero.play_clicked.connect(self.play_featured.emit)
        v.addWidget(self._hero)

        # ── Continue Watching ────────────────────────────────────────
        self._cw = Carousel("Continue Watching", kicker="Where you left off")
        self._cw.open_details.connect(self.open_details.emit)
        v.addWidget(self._cw)

        # ── Trending Now ─────────────────────────────────────────────
        self._trending = Carousel(
            "Trending Now",
            kicker="What's hot",
            show_see_all=True,
        )
        self._trending.open_details.connect(self.open_details.emit)
        self._trending.see_all.connect(lambda: self.request_search.emit(""))
        v.addWidget(self._trending)

        # ── New & Noteworthy (per provider) ─────────────────────────
        self._fresh = Carousel(
            "New & Noteworthy",
            kicker="Fresh picks",
        )
        self._fresh.open_details.connect(self.open_details.emit)
        v.addWidget(self._fresh)

        v.addStretch(1)

    # ── refresh on focus ─────────────────────────────────────────────────

    def refresh(self) -> None:
        self._refresh_continue_watching()
        # Local DB above is always refreshed; remote rows only when stale
        # or still empty (e.g. the first fetch failed offline).
        now = time.monotonic()
        stale = now - self._last_remote_refresh > _REMOTE_TTL_SECONDS
        if stale or self._trending.is_empty():
            self._last_remote_refresh = now
            self._refresh_trending()
        if stale or self._fresh.is_empty():
            self._refresh_fresh()

    def _refresh_continue_watching(self) -> None:
        history = get_library().list_history(limit=12)
        items = [
            AnimeSummary(
                provider_id=h.provider_id,
                url=h.anime_url,
                title=h.title or h.anime_url,
                poster_url=h.poster_url,
            )
            for h in history
        ]
        self._cw.populate(items)
        self._cw.setVisible(bool(items))

    def _refresh_trending(self) -> None:
        run_async(
            self._fetch_pool(TRENDING_SEEDS[:3], limit=10),
            on_done=lambda items: (self._trending.populate(items), self._hero.set_pool(items)),
            on_error=lambda _e: None,
        )

    def _refresh_fresh(self) -> None:
        run_async(
            self._fetch_pool(TRENDING_SEEDS[3:], limit=8),
            on_done=lambda items: self._fresh.populate(items),
            on_error=lambda _e: None,
        )

    async def _fetch_pool(self, seeds, *, limit: int) -> list[AnimeSummary]:
        if not provider_registry:
            return []
        providers = list(provider_registry.values())
        # Fire every (seed × provider) query concurrently instead of
        # awaiting them one-by-one — a cold home page used to block on a
        # serial chain of network round-trips.
        chunks = await asyncio.gather(
            *(p.search(seed, limit=limit) for seed in seeds for p in providers),
            return_exceptions=True,
        )
        # de-dup, preserving the seed-major / provider-minor ordering
        seen: set[tuple[str, str]] = set()
        unique: list[AnimeSummary] = []
        for chunk in chunks:
            if not isinstance(chunk, list):
                continue
            for s in chunk:
                k = (s.provider_id, s.url)
                if k in seen:
                    continue
                seen.add(k)
                unique.append(s)
                if len(unique) >= 24:
                    return unique
        return unique


# ─── hero widget ───────────────────────────────────────────────────────────


class _Hero(QFrame):
    explore_clicked = Signal()
    play_clicked = Signal(object)
    info_clicked = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setFixedHeight(560)
        self.setStyleSheet("background: transparent;")
        self._featured: AnimeSummary | None = None

        # backdrop label sits behind everything
        self._backdrop = QLabel(self)
        self._backdrop.setScaledContents(False)
        self._backdrop.lower()
        self._backdrop.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            "stop:0 #14141C, stop:1 #050507);"
        )

        # gradient fade label on top of backdrop — strong on the bottom
        # so the kicker/title/buttons remain legible over busy artwork.
        self._fade = QLabel(self)
        self._fade.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            "stop:0 rgba(0,0,0,90), stop:0.35 rgba(0,0,0,30),"
            "stop:0.7 rgba(0,0,0,160), stop:1 rgba(0,0,0,255));"
        )

        # foreground content
        inner = QFrame(self)
        inner.setStyleSheet("background: transparent;")
        v = QVBoxLayout(inner)
        v.setContentsMargins(64, 60, 64, 56)
        v.setSpacing(10)

        # push content to the BOTTOM-LEFT, Apple-TV-style
        v.addStretch(1)

        self._kicker = QLabel("FEATURED ANIME")
        self._kicker.setObjectName("kicker")
        v.addWidget(self._kicker)

        self._title = QLabel("Discover what's new on Anisync")
        self._title.setObjectName("display")
        self._title.setWordWrap(True)
        self._title.setMaximumWidth(900)
        v.addWidget(self._title)

        self._desc = QLabel("Stream and download from every supported source in one beautiful place.")
        self._desc.setStyleSheet("font-size:15px; color:#D0D0DA;")
        self._desc.setWordWrap(True)
        self._desc.setMaximumWidth(720)
        v.addWidget(self._desc)

        v.addSpacing(18)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        self._play_btn = QPushButton("Play")
        self._play_btn.setIcon(play_icon())
        self._play_btn.setObjectName("primary")
        self._play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        # Unlike "More info", Play opens Details with autoplay — the first
        # episode starts as soon as the episode list is loaded.
        self._play_btn.clicked.connect(lambda: self._featured and self.play_clicked.emit(self._featured))
        btn_row.addWidget(self._play_btn)

        self._info_btn = QPushButton("More info")
        self._info_btn.setObjectName("outlined")
        self._info_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._info_btn.clicked.connect(lambda: self._featured and self.info_clicked.emit(self._featured))
        btn_row.addWidget(self._info_btn)

        self._explore_btn = QPushButton("Explore catalog")
        self._explore_btn.setObjectName("ghost")
        self._explore_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._explore_btn.clicked.connect(self.explore_clicked.emit)
        btn_row.addWidget(self._explore_btn)

        btn_row.addStretch(1)
        v.addLayout(btn_row)

        self._inner = inner

    def set_pool(self, items: list[AnimeSummary]) -> None:
        if not items:
            return
        # prefer items with a poster
        with_poster = [i for i in items if i.poster_url]
        choice = random.choice(with_poster or items)
        self._featured = choice
        self._kicker.setText(f"FEATURED · {choice.provider_id.upper()}")
        self._title.setText(choice.title)
        meta = []
        if choice.year: meta.append(str(choice.year))
        if choice.type: meta.append(choice.type)
        if choice.episodes_count: meta.append(f"{choice.episodes_count} episodes")
        self._desc.setText(" · ".join(meta) or "Tap More info to view details.")

        # connect Play → emit info_clicked (Details will start playback)
        if choice.poster_url:
            loader = PosterLoader(choice.poster_url)
            loader.loaded.connect(self._apply_backdrop)
            loader.start()
            self._loader = loader  # keep ref
        fade_in(self._inner, duration=320)

    def _apply_backdrop(self, data: bytes) -> None:
        if not data:
            return
        pix = QPixmap()
        if not pix.loadFromData(data):
            return
        scaled = pix.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._backdrop.setPixmap(scaled)

    def resizeEvent(self, evt):  # noqa: N802
        super().resizeEvent(evt)
        self._backdrop.setGeometry(0, 0, self.width(), self.height())
        self._fade.setGeometry(0, 0, self.width(), self.height())
        self._inner.setGeometry(0, 0, self.width(), self.height())
