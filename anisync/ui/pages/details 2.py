"""Anime details page: poster, synopsis, episode grid, library actions."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from anisync.core.library import get_library
from anisync.core.models import Anime, AnimeSummary, Episode, ListKind
from anisync.core.registry import provider_registry
from anisync.utils.async_runner import run_async
from anisync.ui.widgets.poster_loader import PosterLoader


class DetailsPage(QWidget):
    play_episode = Signal(object, object)         # Anime, Episode
    download_episode = Signal(object, object)     # Anime, Episode
    error = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._anime: Anime | None = None
        self._episodes: list[Episode] = []
        self._watched: set[int] = set()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(self._scroll)

        self._content = QWidget()
        self._scroll.setWidget(self._content)

        self._layout = QVBoxLayout(self._content)
        self._layout.setContentsMargins(32, 24, 32, 24)
        self._layout.setSpacing(16)

        self._show_empty()

    def _show_empty(self) -> None:
        self._clear()
        lbl = QLabel("Select an anime from search or library.")
        lbl.setObjectName("muted")
        self._layout.addWidget(lbl)
        self._layout.addStretch(1)

    def _clear(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
            else:
                layout = item.layout()
                if layout:
                    self._delete_layout(layout)

    def _delete_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    # ─── load ─────────────────────────────────────────────────────────────

    def load(self, summary: AnimeSummary) -> None:
        self._clear()
        self._layout.addWidget(QLabel("Loading…"))
        provider = provider_registry.get(summary.provider_id)
        if provider is None:
            self.error.emit(f"Unknown provider: {summary.provider_id}")
            return

        async def fetch():
            anime = await provider.get_anime(summary.url)
            episodes = await provider.list_episodes(anime)
            return anime, episodes

        run_async(
            fetch(),
            on_done=lambda res: self._render(*res),
            on_error=lambda e: self.error.emit(f"Load failed: {e}"),
        )

    def _render(self, anime: Anime, episodes: list[Episode]) -> None:
        self._anime = anime
        self._episodes = episodes
        lib = get_library()
        lib.cache_anime(anime)
        self._watched = lib.episodes_watched(anime.provider_id, anime.url)

        self._clear()

        # ── header ──
        header = QHBoxLayout()
        header.setSpacing(20)

        poster = QLabel()
        poster.setFixedSize(220, 320)
        poster.setStyleSheet("background:#000; border-radius:8px;")
        poster.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._poster_loader = PosterLoader(anime.poster_url)
        self._poster_loader.loaded.connect(
            lambda data, lbl=poster: _apply_pixmap(lbl, data)
        )
        self._poster_loader.start()
        header.addWidget(poster, 0, Qt.AlignmentFlag.AlignTop)

        info = QVBoxLayout()
        info.setSpacing(8)
        title = QLabel(anime.title)
        title.setObjectName("h1")
        title.setWordWrap(True)
        info.addWidget(title)

        meta_bits = []
        if anime.year:
            meta_bits.append(str(anime.year))
        if anime.type:
            meta_bits.append(anime.type)
        if anime.status:
            meta_bits.append(anime.status)
        if anime.episodes_count:
            meta_bits.append(f"{anime.episodes_count} ep")
        if anime.rating:
            meta_bits.append(f"★ {anime.rating:.1f}")
        meta = QLabel(" · ".join(meta_bits))
        meta.setObjectName("muted")
        info.addWidget(meta)

        if anime.genres:
            genres = QLabel(", ".join(anime.genres))
            genres.setObjectName("muted")
            info.addWidget(genres)

        desc = QLabel(anime.description or "")
        desc.setWordWrap(True)
        info.addWidget(desc)

        btns = QHBoxLayout()
        btns.setSpacing(10)

        if episodes:
            play_btn = QPushButton("▶  Play")
            play_btn.setProperty("accent", True)
            play_btn.clicked.connect(
                lambda: self.play_episode.emit(anime, episodes[0])
            )
            btns.addWidget(play_btn)

        fav_btn = QPushButton(
            "★ In favorites"
            if lib.is_in_list(anime.provider_id, anime.url, ListKind.FAVORITE)
            else "☆ Add to favorites"
        )
        fav_btn.clicked.connect(lambda: self._toggle_favorite(fav_btn))
        btns.addWidget(fav_btn)

        watch_btn = QPushButton(
            "Remove from Watching"
            if lib.is_in_list(anime.provider_id, anime.url, ListKind.WATCHING)
            else "Mark as Watching"
        )
        watch_btn.clicked.connect(lambda: self._toggle_list(watch_btn, ListKind.WATCHING, "Watching"))
        btns.addWidget(watch_btn)

        btns.addStretch(1)
        info.addLayout(btns)
        info.addStretch(1)

        wrap = QFrame()
        wrap.setLayout(info)
        wrap.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        header.addWidget(wrap, 1)
        self._layout.addLayout(header)

        # ── episodes ──
        ep_label = QLabel(f"Episodes ({len(episodes)})")
        ep_label.setObjectName("h2")
        self._layout.addWidget(ep_label)

        grid = QGridLayout()
        grid.setSpacing(8)
        for i, ep in enumerate(episodes):
            grid.addWidget(self._episode_button(ep), i // 8, i % 8)
        wrapper = QWidget()
        wrapper.setLayout(grid)
        self._layout.addWidget(wrapper)

        self._layout.addStretch(1)

    def _episode_button(self, ep: Episode) -> QWidget:
        frame = QFrame()
        frame.setObjectName("card")
        frame.setFixedSize(140, 90)
        v = QVBoxLayout(frame)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(2)
        num = QLabel(f"Episode {ep.number}")
        num.setObjectName("cardTitle")
        v.addWidget(num)
        if ep.dub:
            d = QLabel(ep.dub)
            d.setObjectName("cardMeta")
            v.addWidget(d)
        if ep.number in self._watched:
            mark = QLabel("● watched")
            mark.setObjectName("muted")
            v.addWidget(mark)
        v.addStretch(1)

        row = QHBoxLayout()
        row.setSpacing(4)
        play = QPushButton("▶")
        play.setFixedHeight(22)
        play.setProperty("accent", True)
        play.clicked.connect(lambda: self.play_episode.emit(self._anime, ep))
        row.addWidget(play)

        dl = QPushButton("⬇")
        dl.setFixedHeight(22)
        dl.clicked.connect(lambda: self.download_episode.emit(self._anime, ep))
        row.addWidget(dl)
        v.addLayout(row)
        return frame

    # ─── actions ──────────────────────────────────────────────────────────

    def _toggle_favorite(self, btn: QPushButton) -> None:
        if not self._anime:
            return
        lib = get_library()
        if lib.is_in_list(self._anime.provider_id, self._anime.url, ListKind.FAVORITE):
            lib.remove_from_list(self._anime.provider_id, self._anime.url, ListKind.FAVORITE)
            btn.setText("☆ Add to favorites")
        else:
            lib.add_to_list(self._anime, ListKind.FAVORITE)
            btn.setText("★ In favorites")

    def _toggle_list(self, btn: QPushButton, kind: ListKind, name: str) -> None:
        if not self._anime:
            return
        lib = get_library()
        if lib.is_in_list(self._anime.provider_id, self._anime.url, kind):
            lib.remove_from_list(self._anime.provider_id, self._anime.url, kind)
            btn.setText(f"Mark as {name}")
        else:
            lib.add_to_list(self._anime, kind)
            btn.setText(f"Remove from {name}")


def _apply_pixmap(label: QLabel, data: bytes) -> None:
    if not data:
        return
    pix = QPixmap()
    if pix.loadFromData(data):
        label.setPixmap(
            pix.scaled(
                label.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
