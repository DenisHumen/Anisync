"""Main window — Apple TV / Crunchyroll style.

Layout (z-order back→front):
1. ``CinemaBackground`` — static cinematic gradient + corner glows.
2. ``TopNav`` strip pinned at the top, then the stacked content area.
3. ``Snackbar`` overlay (bottom-centered toast).

The window is frameless + translucent so the cinematic background reads
edge-to-edge with no platform chrome. Window dragging is handled by
TopNav; edge resize by a small event filter on the central widget.
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QEvent, QPoint, QRect, Qt
from PySide6.QtGui import QCursor, QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from anisync.core.config import Config
from anisync.core.downloader import get_manager
from anisync.core.library import get_library
from anisync.core.models import Anime, Episode
from anisync.core.updater import ReleaseInfo, UpdateService
from anisync.ui.dialogs.update_dialog import UpdateDialog
from anisync.ui.glass import CinemaBackground
from anisync.ui.pages.auth import AuthPage
from anisync.ui.pages.details import DetailsPage
from anisync.ui.pages.downloads import DownloadsPage
from anisync.ui.pages.history import HistoryPage
from anisync.ui.pages.home import HomePage
from anisync.ui.pages.library import LibraryPage
from anisync.ui.pages.player import PlayerPage
from anisync.ui.pages.search import SearchPage
from anisync.ui.pages.settings import SettingsPage
from anisync.ui.theme import PALETTE, build_qss
from anisync.ui.widgets.snackbar import Snackbar
from anisync.ui.widgets.topnav import TopNav
from anisync.utils.async_runner import run_async


_RESIZE_MARGIN = 6


# Nav keys must match what TopNav emits.
NAV_ITEMS = [
    ("home",      "Home"),
    ("search",    "Search"),
    ("library",   "Library"),
    ("downloads", "Downloads"),
    ("account",   "Account"),
    ("settings",  "Settings"),
]


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Anisync")
        self.resize(1440, 900)
        self.setMinimumSize(1024, 640)
        self.setStyleSheet(build_qss(PALETTE))

        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        # bootstrap services
        get_library()
        get_manager()

        central = QWidget()
        central.setMouseTracking(True)
        self.setCentralWidget(central)

        # cinematic backdrop layer
        self._bg = CinemaBackground(central)
        self._bg.lower()

        # foreground root frame
        self._root = QFrame(central)
        self._root.setObjectName("root")
        self._root.setMouseTracking(True)
        self._root.installEventFilter(self)

        outer = QVBoxLayout(self._root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # top navigation
        self._nav = TopNav(NAV_ITEMS, self)
        self._nav.nav_clicked.connect(self._navigate)
        self._nav.search_clicked.connect(lambda: self._navigate("search"))
        outer.addWidget(self._nav)

        # stacked pages
        self._pages = QStackedWidget()
        self._pages.setStyleSheet("background: transparent;")
        outer.addWidget(self._pages, 1)

        # ── build pages ─────────────────────────────────────────────
        self.home      = HomePage()
        self.search    = SearchPage()
        self.details   = DetailsPage()
        self.player    = PlayerPage()
        self.library   = LibraryPage()
        self.history   = HistoryPage()
        self.downloads = DownloadsPage()
        self.account   = AuthPage()
        self.settings  = SettingsPage()

        self._page_keys: dict[str, QWidget] = {
            "home":      self.home,
            "search":    self.search,
            "library":   self.library,
            "history":   self.history,
            "downloads": self.downloads,
            "account":   self.account,
            "settings":  self.settings,
            "player":    self.player,
            "details":   self.details,
        }
        self._refreshers: dict[str, Callable[[], None]] = {
            "home":      self.home.refresh,
            "library":   self.library.refresh,
            "history":   self.history.refresh,
            "downloads": self.downloads.refresh,
        }
        for key, w in self._page_keys.items():
            self._pages.addWidget(w)

        # ── wiring ──────────────────────────────────────────────────
        self.home.open_details.connect(self._open_details)
        self.home.request_search.connect(self._go_search)
        self.search.open_details.connect(self._open_details)
        self.search.play_request.connect(self._play)
        self.search.error.connect(lambda msg: self._snackbar.show_message(msg, level="error"))
        self.details.play_episode.connect(self._play)
        self.details.download_episode.connect(self._download)
        self.details.error.connect(lambda msg: self._snackbar.show_message(msg, level="error"))
        self.library.open_details.connect(self._open_details)
        self.library.request_search.connect(self._go_search)
        self.history.open_details.connect(self._open_details)
        self.player.error.connect(lambda msg: self._snackbar.show_message(msg, level="error"))
        self.player.back_requested.connect(lambda: self._navigate("home"))

        # snackbar
        self._snackbar = Snackbar(central)
        self._snackbar.setFixedWidth(440)
        self._snackbar.hide()

        mgr = get_manager()
        mgr.signals.enqueued.connect(
            lambda t: self._snackbar.show_message(
                f"Queued · {t.anime_title} · E{t.episode_number}", level="success"
            )
        )
        mgr.signals.completed.connect(
            lambda tid: self._snackbar.show_message(f"Download complete (#{tid})", level="success")
        )
        mgr.signals.failed.connect(
            lambda tid, msg: self._snackbar.show_message(f"Download failed: {msg}", level="error")
        )

        # Resume downloads interrupted by a previous run (best-effort).
        run_async(mgr.resume_pending(), on_error=lambda _e: None)

        self._navigate("home")
        self._relayout_overlays()

        # resize-by-edge state
        self._resize_edge: int | None = None
        self._resize_start_geom: QRect | None = None
        self._resize_start_pos: QPoint | None = None

        # check for updates
        self._maybe_check_updates()

    # ── navigation ────────────────────────────────────────────────────────

    def _navigate(self, key: str) -> None:
        widget = self._page_keys.get(key)
        if widget is None:
            return
        # Stop playback whenever we leave the player page (audio kept
        # running in the background otherwise).
        if self._pages.currentWidget() is self.player and widget is not self.player:
            self.player.stop()
        self._pages.setCurrentWidget(widget)
        self._nav.set_active(key if key in dict(NAV_ITEMS) else "")
        refresh = self._refreshers.get(key)
        if refresh:
            refresh()

    def _open_details(self, summary) -> None:
        if self._pages.currentWidget() is self.player:
            self.player.stop()
        self.details.load(summary)
        self._pages.setCurrentWidget(self.details)
        # keep no nav active (Details is a sub-view)
        self._nav.set_active("")

    def _go_search(self, query: str) -> None:
        self._navigate("search")
        if query:
            self.search.set_query(query)

    def _play(self, anime: Anime, episode: Episode, playlist: list[Episode] | None = None) -> None:
        self._pages.setCurrentWidget(self.player)
        self._nav.set_active("")
        self.player.play(anime, episode, playlist or [episode])

    def _download(self, anime: Anime, episode: Episode) -> None:
        cfg = Config.load()
        run_async(
            get_manager().enqueue(episode, anime.title, quality=cfg.preferred_quality),
            on_done=lambda _t: None,
            on_error=lambda e: self._snackbar.show_message(f"Download failed: {e}", level="error"),
        )

    # ── updater ───────────────────────────────────────────────────────────

    def _maybe_check_updates(self) -> None:
        cfg = Config.load()
        if not cfg.check_updates_on_start:
            return
        run_async(
            UpdateService(cfg.update_repo).check(),
            on_done=self._on_update_check,
            on_error=lambda _e: None,
        )

    def _on_update_check(self, release: ReleaseInfo | None) -> None:
        if release is None:
            return
        UpdateDialog(release, self).exec()

    # ── layout ────────────────────────────────────────────────────────────

    def resizeEvent(self, evt):  # noqa: N802
        super().resizeEvent(evt)
        self._relayout_overlays()

    def _relayout_overlays(self) -> None:
        c = self.centralWidget()
        if not c:
            return
        rect = c.rect()
        self._bg.setGeometry(rect)
        self._root.setGeometry(rect)
        sb = self._snackbar
        sb.move((rect.width() - sb.width()) // 2,
                rect.height() - sb.sizeHint().height() - 28)

    # ── frameless resize-by-edge ──────────────────────────────────────────

    def eventFilter(self, obj, evt):  # noqa: N802
        if obj is self._root and not self.isMaximized() and not self.isFullScreen():
            t = evt.type()
            if t == QEvent.Type.MouseMove:
                self._update_resize_cursor(evt)
            elif t == QEvent.Type.MouseButtonPress and isinstance(evt, QMouseEvent):
                if evt.button() == Qt.MouseButton.LeftButton:
                    edge = self._edge_at(evt.position().toPoint())
                    if edge:
                        self._resize_edge = edge
                        self._resize_start_geom = self.frameGeometry()
                        self._resize_start_pos = evt.globalPosition().toPoint()
                        return True
            elif t == QEvent.Type.MouseButtonRelease:
                self._resize_edge = None
                self._resize_start_geom = None
                self._resize_start_pos = None
        return super().eventFilter(obj, evt)

    def mouseMoveEvent(self, evt):  # noqa: N802
        if self._resize_edge is not None and self._resize_start_geom and self._resize_start_pos:
            self._perform_edge_resize(evt.globalPosition().toPoint())
            return
        super().mouseMoveEvent(evt)

    def _edge_at(self, pos: QPoint) -> int | None:
        r = self._root.rect()
        m = _RESIZE_MARGIN
        edge = 0
        if pos.x() <= m:                  edge |= 0b0001
        if pos.x() >= r.width()  - m:     edge |= 0b0010
        if pos.y() <= m:                  edge |= 0b0100
        if pos.y() >= r.height() - m:     edge |= 0b1000
        return edge or None

    def _update_resize_cursor(self, evt) -> None:
        edge = self._edge_at(evt.position().toPoint())
        cursors = {
            0b0001: Qt.CursorShape.SizeHorCursor,
            0b0010: Qt.CursorShape.SizeHorCursor,
            0b0100: Qt.CursorShape.SizeVerCursor,
            0b1000: Qt.CursorShape.SizeVerCursor,
            0b0101: Qt.CursorShape.SizeFDiagCursor,
            0b1010: Qt.CursorShape.SizeFDiagCursor,
            0b0110: Qt.CursorShape.SizeBDiagCursor,
            0b1001: Qt.CursorShape.SizeBDiagCursor,
        }
        if edge and edge in cursors:
            self._root.setCursor(QCursor(cursors[edge]))
        else:
            self._root.unsetCursor()

    def _perform_edge_resize(self, global_pos: QPoint) -> None:
        edge = self._resize_edge
        geom = QRect(self._resize_start_geom)
        dx = global_pos.x() - self._resize_start_pos.x()
        dy = global_pos.y() - self._resize_start_pos.y()
        mw, mh = self.minimumWidth(), self.minimumHeight()
        if edge & 0b0001:
            nl = geom.left() + dx
            if geom.right() - nl + 1 < mw: nl = geom.right() - mw + 1
            geom.setLeft(nl)
        if edge & 0b0010:
            nr = geom.right() + dx
            if nr - geom.left() + 1 < mw: nr = geom.left() + mw - 1
            geom.setRight(nr)
        if edge & 0b0100:
            nt = geom.top() + dy
            if geom.bottom() - nt + 1 < mh: nt = geom.bottom() - mh + 1
            geom.setTop(nt)
        if edge & 0b1000:
            nb = geom.bottom() + dy
            if nb - geom.top() + 1 < mh: nb = geom.top() + mh - 1
            geom.setBottom(nb)
        self.setGeometry(geom)

    # ── lifecycle ─────────────────────────────────────────────────────────

    def closeEvent(self, evt):  # noqa: N802
        self.player.stop()
        super().closeEvent(evt)
