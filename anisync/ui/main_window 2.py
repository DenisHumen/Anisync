"""Main application window: sidebar + stacked content + snackbar overlay."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from anisync.core.config import Config
from anisync.core.downloader import get_manager
from anisync.core.library import get_library
from anisync.core.models import Anime, Episode
from anisync.ui.pages.details import DetailsPage
from anisync.ui.pages.downloads import DownloadsPage
from anisync.ui.pages.history import HistoryPage
from anisync.ui.pages.home import HomePage
from anisync.ui.pages.library import LibraryPage
from anisync.ui.pages.player import PlayerPage
from anisync.ui.pages.search import SearchPage
from anisync.ui.pages.settings import SettingsPage
from anisync.ui.theme import PALETTE, build_qss
from anisync.utils.async_runner import run_async
from anisync.ui.widgets.snackbar import Snackbar


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Anisync")
        self.resize(1380, 860)
        self.setStyleSheet(build_qss(PALETTE))
        # Make sure DB + downloader exist
        get_library()
        get_manager()

        central = QWidget()
        self.setCentralWidget(central)
        hl = QHBoxLayout(central)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(0)

        # Sidebar
        self._sidebar = QWidget()
        self._sidebar.setObjectName("sidebar")
        self._sidebar.setFixedWidth(220)
        sv = QVBoxLayout(self._sidebar)
        sv.setContentsMargins(12, 12, 12, 12)
        sv.setSpacing(4)

        logo = QLabel("ANISYNC")
        logo.setObjectName("logo")
        sv.addWidget(logo)

        self._nav_buttons: list[QPushButton] = []
        self._pages = QStackedWidget()

        # Build pages
        self.home = HomePage()
        self.search = SearchPage()
        self.details = DetailsPage()
        self.player = PlayerPage()
        self.library = LibraryPage()
        self.history = HistoryPage()
        self.downloads = DownloadsPage()
        self.settings = SettingsPage()

        self._add_nav(sv, "🏠  Home", self.home, refresh=self.home.refresh)
        self._add_nav(sv, "🔍  Search", self.search)
        self._add_nav(sv, "📚  Library", self.library, refresh=self.library.refresh)
        self._add_nav(sv, "🕒  History", self.history, refresh=self.history.refresh)
        self._add_nav(sv, "⬇  Downloads", self.downloads, refresh=self.downloads.refresh)
        self._add_nav(sv, "▶  Player", self.player)
        self._add_nav(sv, "⚙  Settings", self.settings)
        # Details is not in nav, accessed via cards.
        self._pages.addWidget(self.details)

        sv.addStretch(1)
        version = QLabel("v0.1 · alpha")
        version.setObjectName("muted")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sv.addWidget(version)

        hl.addWidget(self._sidebar)
        hl.addWidget(self._pages, 1)

        # Snackbar
        self._snackbar = Snackbar(self)
        self._snackbar.setFixedWidth(420)

        # Wiring
        self.home.open_details.connect(self._open_details)
        self.home.request_search.connect(self._go_search)
        self.search.open_details.connect(self._open_details)
        self.search.error.connect(lambda msg: self._snackbar.show_message(msg, level="error"))
        self.details.play_episode.connect(self._play)
        self.details.download_episode.connect(self._download)
        self.details.error.connect(lambda msg: self._snackbar.show_message(msg, level="error"))
        self.library.open_details.connect(self._open_details)
        self.history.open_details.connect(self._open_details)
        self.player.error.connect(lambda msg: self._snackbar.show_message(msg, level="error"))

        # Select first nav
        if self._nav_buttons:
            self._activate_button(self._nav_buttons[0])

    # ─── nav ──────────────────────────────────────────────────────────────

    def _add_nav(
        self,
        sv: QVBoxLayout,
        text: str,
        page: QWidget,
        *,
        refresh: Callable[[], None] | None = None,
    ) -> None:
        btn = QPushButton(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        sv.addWidget(btn)
        idx = self._pages.addWidget(page)
        def go():
            self._pages.setCurrentIndex(idx)
            self._activate_button(btn)
            if refresh:
                refresh()
        btn.clicked.connect(go)
        self._nav_buttons.append(btn)

    def _activate_button(self, active: QPushButton) -> None:
        for b in self._nav_buttons:
            b.setProperty("active", b is active)
            b.style().unpolish(b)
            b.style().polish(b)

    # ─── navigation helpers ───────────────────────────────────────────────

    def _open_details(self, summary) -> None:
        self._pages.setCurrentWidget(self.details)
        self._activate_button(self._nav_buttons[0])  # no nav for details; leave Home highlight
        self.details.load(summary)

    def _go_search(self, query: str) -> None:
        for i, btn in enumerate(self._nav_buttons):
            if "Search" in btn.text():
                btn.click()
                break
        if query:
            self.search.set_query(query)

    def _play(self, anime: Anime, episode: Episode) -> None:
        # Switch to player page
        for btn in self._nav_buttons:
            if "Player" in btn.text():
                btn.click()
                break
        self.player.play(anime, episode)

    def _download(self, anime: Anime, episode: Episode) -> None:
        cfg = Config.load()
        run_async(
            get_manager().enqueue(episode, anime.title, quality=cfg.preferred_quality),
            on_done=lambda _t: self._snackbar.show_message(
                f"Queued: {anime.title} — Episode {episode.number}", level="success"
            ),
            on_error=lambda e: self._snackbar.show_message(f"Download failed: {e}", level="error"),
        )

    # ─── layout overrides ─────────────────────────────────────────────────

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        # Position snackbar at bottom center
        if self._snackbar.isVisible() or True:
            x = (self.width() - self._snackbar.width()) // 2
            y = self.height() - self._snackbar.sizeHint().height() - 24
            self._snackbar.move(x, y)

    def closeEvent(self, event):  # noqa: N802
        self.player.stop()
        super().closeEvent(event)
