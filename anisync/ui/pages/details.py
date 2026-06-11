"""Anime details page — cinematic hero + episode list.

Layout:

* Full-width hero with backdrop + poster + title/meta/Play.
* Episode list grouped by dub track (when multiple dubs exist) as
  Apple-TV-style horizontal carousels of episode tiles.
"""
from __future__ import annotations

from collections import defaultdict

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QPixmap
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

from anisync.core.config import Config
from anisync.core.library import get_library
from anisync.core.models import Anime, AnimeSummary, Episode, ListKind
from anisync.core.registry import provider_registry
from anisync.utils.async_runner import run_async
from anisync.ui.widgets.icons import play_icon
from anisync.ui.widgets.poster_loader import PosterLoader
from anisync.ui.widgets.spinner import LoadingPanel


# ─── Episode tile ──────────────────────────────────────────────────────────


class EpisodeTile(QFrame):
    play_clicked = Signal(object)        # Episode
    download_clicked = Signal(object)

    TILE_W = 240
    THUMB_H = 135                        # 16:9

    def __init__(self, ep: Episode, *, watched: bool, poster_bytes: bytes | None) -> None:
        super().__init__()
        self.ep = ep
        self.setFixedWidth(self.TILE_W)
        self.setStyleSheet("background: transparent;")

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)

        # Thumbnail — poster cropped to 16:9 looks like a backdrop tile
        self._thumb = QLabel()
        self._thumb.setFixedSize(self.TILE_W, self.THUMB_H)
        self._thumb.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            "stop:0 #1A1A22, stop:1 #0D0D12); border-radius: 8px;"
        )
        self._thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if poster_bytes:
            pix = QPixmap()
            if pix.loadFromData(poster_bytes):
                self._thumb.setPixmap(
                    pix.scaled(QSize(self.TILE_W, self.THUMB_H),
                               Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                               Qt.TransformationMode.SmoothTransformation))
        v.addWidget(self._thumb)

        # Episode label
        head = QLabel(f"Episode {ep.number}")
        head.setObjectName("cardTitle")
        v.addWidget(head)

        if ep.dub:
            d = QLabel(ep.dub)
            d.setObjectName("cardMeta")
            v.addWidget(d)

        if watched:
            mark = QLabel("● Watched")
            mark.setStyleSheet("color:#34C759; font-size:11px;")
            v.addWidget(mark)

        # Action row
        row = QHBoxLayout()
        row.setSpacing(6)
        play = QPushButton("Play")
        play.setIcon(play_icon(px=14))
        play.setObjectName("primary")
        play.setCursor(Qt.CursorShape.PointingHandCursor)
        play.clicked.connect(lambda: self.play_clicked.emit(ep))
        row.addWidget(play)

        dl = QPushButton("Save")
        dl.setObjectName("ghost")
        dl.setMinimumWidth(64)
        dl.setToolTip("Download episode")
        dl.setCursor(Qt.CursorShape.PointingHandCursor)
        dl.clicked.connect(lambda: self.download_clicked.emit(ep))
        row.addWidget(dl)
        v.addLayout(row)


# ─── Page ──────────────────────────────────────────────────────────────────


class DetailsPage(QWidget):
    play_episode = Signal(object, object, list)  # Anime, Episode, list[Episode]
    download_episode = Signal(object, object)
    error = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._anime: Anime | None = None
        self._episodes: list[Episode] = []
        self._watched: set[int] = set()
        self._poster_bytes: bytes | None = None
        self._autoplay = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet("background: transparent;")
        outer.addWidget(self._scroll)

        self._content = QWidget()
        self._content.setStyleSheet("background: transparent;")
        self._scroll.setWidget(self._content)

        self._layout = QVBoxLayout(self._content)
        self._layout.setContentsMargins(0, 0, 0, 40)
        self._layout.setSpacing(20)

        self._show_empty()

    # ── empty / clear ──

    def _show_empty(self) -> None:
        self._clear()
        wrap = QWidget()
        wrap.setStyleSheet("background: transparent;")
        v = QVBoxLayout(wrap)
        v.setContentsMargins(64, 80, 64, 64)
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl = QLabel("Select an anime from Search or Library.")
        lbl.setObjectName("muted")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(lbl)
        self._layout.addWidget(wrap)
        self._layout.addStretch(1)

    def _clear(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    # ── load ──

    def load(self, summary: AnimeSummary, *, autoplay: bool = False) -> None:
        self._autoplay = autoplay
        provider = provider_registry.get(summary.provider_id)
        if provider is None:
            self.error.emit(f"Unknown provider: {summary.provider_id}")
            return

        lib = get_library()
        cached = lib.get_cached_full(summary.provider_id, summary.url)

        if cached is not None:
            # Instant paint from cache; refresh quietly in the background.
            anime, episodes, _updated = cached
            self._render(anime, episodes)
            self._refresh_in_background(provider, summary)
            return

        # No cache → show a nice spinner while the first fetch runs.
        self._clear()
        self._loading = LoadingPanel(f"Loading {summary.title}…")
        self._layout.addWidget(self._loading)
        self._layout.addStretch(1)

        async def fetch():
            anime = await provider.get_anime(summary.url)
            episodes = await provider.list_episodes(anime)
            return anime, episodes

        run_async(
            fetch(),
            on_done=lambda res: self._render(*res),
            on_error=lambda e: self.error.emit(f"Load failed: {e}"),
        )

    def _refresh_in_background(self, provider, summary: AnimeSummary) -> None:
        async def fetch():
            anime = await provider.get_anime(summary.url)
            episodes = await provider.list_episodes(anime)
            return anime, episodes

        def _maybe_update(res):
            anime, episodes = res
            # Only re-render if the dataset actually changed — avoids flicker.
            old_ids = [(e.number, e.dub, e.embed_url) for e in self._episodes]
            new_ids = [(e.number, e.dub, e.embed_url) for e in episodes]
            if old_ids != new_ids or (self._anime and self._anime.title != anime.title):
                self._render(anime, episodes)
            else:
                # still refresh the cached blob with the latest metadata
                get_library().cache_anime_full(anime, episodes)

        run_async(fetch(), on_done=_maybe_update, on_error=lambda _e: None)

    # ── render ──

    def _render(self, anime: Anime, episodes: list[Episode]) -> None:
        self._anime = anime
        self._episodes = episodes
        lib = get_library()
        lib.cache_anime(anime)
        lib.cache_anime_full(anime, episodes)
        self._watched = lib.episodes_watched(anime.provider_id, anime.url)

        self._clear()
        self._layout.addWidget(self._build_hero(anime))
        self._layout.addWidget(self._build_episodes_section(anime, episodes), 1)
        self._layout.addStretch(1)

        # async poster (used both for hero backdrop fallback and ep thumbnails)
        if anime.poster_url:
            self._poster_loader = PosterLoader(anime.poster_url)
            self._poster_loader.loaded.connect(self._poster_loaded)
            self._poster_loader.start()

        # Hero "Play" on the home page lands here with autoplay=True:
        # start the first episode as soon as the data is on screen.
        if self._autoplay:
            self._autoplay = False
            ep = self._first_episode()
            if ep is not None:
                self.play_episode.emit(anime, ep, list(episodes))

    def _first_episode(self) -> Episode | None:
        """First episode to play, honouring the preferred-dub setting."""
        if not self._episodes:
            return None
        pref = Config.load().preferred_dub.strip().lower()
        if pref:
            matching = [
                e for e in self._episodes if e.dub and pref in e.dub.lower()
            ]
            if matching:
                return min(matching, key=lambda e: e.number)
        return self._episodes[0]

    def _poster_loaded(self, data: bytes) -> None:
        self._poster_bytes = data or None
        # re-render episodes so tiles get the thumbnail
        if self._anime is not None:
            self._render_episodes_only()

    def _render_episodes_only(self) -> None:
        # replace just the episodes section (last widget before stretch)
        # simpler: full re-render
        if self._anime is None:
            return
        # take last item (stretch), remove it
        # find episodes widget by tag
        for i in range(self._layout.count()):
            item = self._layout.itemAt(i)
            w = item.widget()
            if w and w.property("eps_section"):
                self._layout.removeWidget(w)
                w.deleteLater()
                new = self._build_episodes_section(self._anime, self._episodes)
                self._layout.insertWidget(i, new, 1)
                return

    # ── hero ──

    def _build_hero(self, anime: Anime) -> QWidget:
        hero = QFrame()
        hero.setFixedHeight(360)
        hero.setStyleSheet("background: transparent;")

        # Layered: backdrop + gradient + content
        backdrop = QLabel(hero)
        backdrop.setStyleSheet("background:#0A0A0F;")
        fade = QLabel(hero)
        fade.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            "stop:0 rgba(0,0,0,160), stop:0.6 rgba(0,0,0,180), stop:1 rgba(0,0,0,255));"
        )
        hero._backdrop = backdrop  # type: ignore[attr-defined]
        hero._fade = fade  # type: ignore[attr-defined]

        body = QFrame(hero)
        body.setStyleSheet("background: transparent;")
        h = QHBoxLayout(body)
        h.setContentsMargins(64, 28, 64, 28)
        h.setSpacing(28)

        poster = QLabel()
        poster.setFixedSize(200, 300)
        poster.setStyleSheet("background:#16161A; border-radius:10px;")
        poster.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if anime.poster_url:
            loader = PosterLoader(anime.poster_url)
            loader.loaded.connect(lambda data: _apply_pixmap(poster, data) or _apply_backdrop(backdrop, data))
            loader.start()
            hero._poster_loader = loader  # type: ignore[attr-defined]
        h.addWidget(poster, 0, Qt.AlignmentFlag.AlignTop)

        info = QVBoxLayout()
        info.setSpacing(8)

        kicker_bits = [b for b in [anime.year and str(anime.year), anime.type, anime.status] if b]
        kicker = QLabel(" · ".join(kicker_bits) or "Anime")
        kicker.setObjectName("kicker")
        info.addWidget(kicker)

        title = QLabel(anime.title)
        title.setObjectName("h1")
        title.setWordWrap(True)
        info.addWidget(title)

        meta_bits = []
        if anime.episodes_count: meta_bits.append(f"{anime.episodes_count} episodes")
        if anime.rating:         meta_bits.append(f"★ {anime.rating:.1f}")
        if anime.genres:         meta_bits.append(", ".join(anime.genres[:3]))
        meta = QLabel(" · ".join(meta_bits))
        meta.setStyleSheet("color:#9A9AA5; font-size:13px;")
        info.addWidget(meta)

        if anime.description:
            desc = QLabel(anime.description.strip())
            desc.setStyleSheet("color:#C0C0CA; font-size:13px;")
            desc.setWordWrap(True)
            desc.setMaximumWidth(720)
            info.addWidget(desc)

        info.addSpacing(6)

        # Buttons
        lib = get_library()
        btns = QHBoxLayout()
        btns.setSpacing(10)
        if self._episodes:
            play_btn = QPushButton("Play")
            play_btn.setIcon(play_icon())
            play_btn.setObjectName("primary")
            play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            play_btn.clicked.connect(self._play_first)
            btns.addWidget(play_btn)

        fav_btn = QPushButton(
            "♥  In favorites"
            if lib.is_in_list(anime.provider_id, anime.url, ListKind.FAVORITE)
            else "♡  Add to favorites"
        )
        fav_btn.setObjectName("outlined")
        fav_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        fav_btn.clicked.connect(lambda: self._toggle_favorite(fav_btn))
        btns.addWidget(fav_btn)

        watch_btn = QPushButton(
            "Remove from Watching"
            if lib.is_in_list(anime.provider_id, anime.url, ListKind.WATCHING)
            else "Mark as Watching"
        )
        watch_btn.setObjectName("ghost")
        watch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        watch_btn.clicked.connect(lambda: self._toggle_list(watch_btn, ListKind.WATCHING, "Watching"))
        btns.addWidget(watch_btn)
        btns.addStretch(1)
        info.addLayout(btns)
        info.addStretch(1)

        info_wrap = QWidget()
        info_wrap.setLayout(info)
        info_wrap.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        h.addWidget(info_wrap, 1)

        # Position layers on resize
        def _do_layout(_evt=None) -> None:
            backdrop.setGeometry(0, 0, hero.width(), hero.height())
            fade.setGeometry(0, 0, hero.width(), hero.height())
            body.setGeometry(0, 0, hero.width(), hero.height())
        hero.resizeEvent = lambda e: (_do_layout(), QFrame.resizeEvent(hero, e))
        _do_layout()

        return hero

    # ── episodes section ──

    def _build_episodes_section(self, anime: Anime, episodes: list[Episode]) -> QWidget:
        section = QFrame()
        section.setProperty("eps_section", True)
        section.setStyleSheet("background: transparent;")
        v = QVBoxLayout(section)
        v.setContentsMargins(64, 8, 64, 0)
        v.setSpacing(14)

        head = QHBoxLayout()
        title = QLabel("Episodes")
        title.setObjectName("h2")
        head.addWidget(title)
        head.addStretch(1)
        v.addLayout(head)

        if not episodes:
            empty = QLabel("No episodes available.")
            empty.setObjectName("muted")
            v.addWidget(empty)
            return section

        # Group by dub, deduplicating same-number entries inside each group.
        groups: dict[str, list[Episode]] = defaultdict(list)
        seen: dict[str, set[int]] = defaultdict(set)
        for ep in episodes:
            key = ep.dub or "Default"
            if ep.number in seen[key]:
                continue
            seen[key].add(ep.number)
            groups[key].append(ep)
        for eps in groups.values():
            eps.sort(key=lambda e: e.number)

        for dub_name, eps in groups.items():
            label_text = (
                f"{dub_name}  ·  {len(eps)} episodes" if len(groups) > 1
                else f"{len(eps)} episodes  ·  {dub_name}"
            )
            dub_label = QLabel(label_text)
            dub_label.setStyleSheet(
                "color:#F47521; font-size:11px; font-weight:700; letter-spacing:2px;"
            )
            v.addWidget(dub_label)

            strip = QScrollArea()
            strip.setWidgetResizable(True)
            strip.setFrameShape(QFrame.Shape.NoFrame)
            strip.setStyleSheet("background: transparent;")
            strip.setFixedHeight(EpisodeTile.THUMB_H + 110)
            strip.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            strip.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

            row_w = QWidget()
            row_w.setStyleSheet("background: transparent;")
            row = QHBoxLayout(row_w)
            row.setContentsMargins(0, 0, 0, 8)
            row.setSpacing(12)
            row.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

            for ep in eps:
                tile = EpisodeTile(
                    ep,
                    watched=ep.number in self._watched,
                    poster_bytes=self._poster_bytes,
                )
                tile.play_clicked.connect(
                    lambda e, a=anime: self.play_episode.emit(a, e, list(self._episodes))
                )
                tile.download_clicked.connect(lambda e, a=anime: self.download_episode.emit(a, e))
                row.addWidget(tile)
            row.addStretch(1)
            strip.setWidget(row_w)
            v.addWidget(strip)

        return section

    # ── actions ──

    def _play_first(self) -> None:
        ep = self._first_episode()
        if self._anime and ep is not None:
            self.play_episode.emit(self._anime, ep, list(self._episodes))

    def _toggle_favorite(self, btn: QPushButton) -> None:
        if not self._anime:
            return
        lib = get_library()
        if lib.is_in_list(self._anime.provider_id, self._anime.url, ListKind.FAVORITE):
            lib.remove_from_list(self._anime.provider_id, self._anime.url, ListKind.FAVORITE)
            btn.setText("♡  Add to favorites")
        else:
            lib.add_to_list(self._anime, ListKind.FAVORITE)
            btn.setText("♥  In favorites")

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


# ─── helpers ──


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


def _apply_backdrop(label: QLabel, data: bytes) -> None:
    if not data:
        return
    pix = QPixmap()
    if pix.loadFromData(data):
        # heavy blur isn't available cheaply; instead use a darkened scaled copy
        scaled = pix.scaled(label.size(),
                            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                            Qt.TransformationMode.SmoothTransformation)
        label.setPixmap(scaled)
