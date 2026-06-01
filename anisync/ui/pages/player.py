"""Plex / Jellyfin-style video player.

* Fullscreen-capable.
* Controls overlay fades out after 2.5 s of mouse inactivity and back in
  on movement (like Plex).
* Big bottom gradient. Top bar shows back, title and episode meta.
* Keyboard shortcuts: Space (play/pause), ← / → (seek 10 s),
  Shift+← / Shift+→ (seek 60 s), F (fullscreen), Esc (exit fullscreen),
  ↑ / ↓ (volume), M (mute).
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QTimer, QUrl, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from anisync.core.config import Config
from anisync.core.library import get_library
from anisync.core.models import Anime, Episode, VideoSource
from anisync.core.registry import resolve_for
from anisync.utils.async_runner import run_async


def _fmt(ms: int) -> str:
    s = max(0, ms // 1000)
    m, sec = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h:d}:{m:02d}:{sec:02d}" if h else f"{m:d}:{sec:02d}"


class PlayerPage(QWidget):
    error = Signal(str)
    back_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._anime: Anime | None = None
        self._episode: Episode | None = None
        self._playlist: list[Episode] = []
        self._sources: list[VideoSource] = []
        self._last_mouse = QPoint(0, 0)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)

        # ── stacked: status placeholder + video ──
        root = QStackedLayout(self)
        root.setStackingMode(QStackedLayout.StackingMode.StackAll)
        root.setContentsMargins(0, 0, 0, 0)
        self._root = root

        self._video = QVideoWidget()
        self._video.setStyleSheet("background:#000;")
        self._video.setMouseTracking(True)
        root.addWidget(self._video)

        # status overlay (covers video when no media)
        self._status_frame = QFrame()
        self._status_frame.setStyleSheet("background:#0A0A12;")
        sv = QVBoxLayout(self._status_frame)
        sv.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status = QLabel("Pick an episode to start watching.")
        self._status.setObjectName("muted")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setStyleSheet("font-size:16px;")
        sv.addWidget(self._status)
        root.addWidget(self._status_frame)
        root.setCurrentWidget(self._status_frame)

        # ── media pipeline (must exist before overlay wires signals) ──
        self._player = QMediaPlayer(self)
        self._audio = QAudioOutput(self)
        self._player.setAudioOutput(self._audio)
        self._player.setVideoOutput(self._video)
        self._audio.setVolume(0.8)

        # ── overlay (top bar + bottom bar) ──
        self._overlay = QFrame(self)
        self._overlay.setObjectName("playerOverlay")
        self._overlay.setMouseTracking(True)
        self._overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self._build_overlay()
        root.addWidget(self._overlay)
        root.setCurrentWidget(self._overlay)
        self._player.positionChanged.connect(self._on_position)
        self._player.durationChanged.connect(self._on_duration)
        self._player.errorOccurred.connect(self._on_error)
        self._player.playbackStateChanged.connect(self._on_state)

        # ── timers ──
        self._save_timer = QTimer(self)
        self._save_timer.setInterval(5000)
        self._save_timer.timeout.connect(self._save_progress)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._hide_overlay)

    # ── overlay construction ──────────────────────────────────────────────

    def _build_overlay(self) -> None:
        wrap = QVBoxLayout(self._overlay)
        wrap.setContentsMargins(20, 16, 20, 16)

        # top bar
        top = QHBoxLayout()
        back = QPushButton("←")
        back.setProperty("icon", True)
        back.setToolTip("Back")
        back.clicked.connect(self.back_requested.emit)
        top.addWidget(back)

        self._title_label = QLabel("")
        self._title_label.setStyleSheet("font-size:16px; font-weight:700;")
        top.addWidget(self._title_label)

        self._ep_label = QLabel("")
        self._ep_label.setObjectName("muted")
        self._ep_label.setContentsMargins(10, 0, 0, 0)
        top.addWidget(self._ep_label)

        top.addStretch(1)

        self._fs_btn = QPushButton("⤢")
        self._fs_btn.setProperty("icon", True)
        self._fs_btn.setToolTip("Toggle fullscreen (F)")
        self._fs_btn.clicked.connect(self._toggle_fullscreen)
        top.addWidget(self._fs_btn)

        wrap.addLayout(top)
        wrap.addStretch(1)

        # bottom: seek + controls
        bottom = QVBoxLayout()
        bottom.setSpacing(8)

        self._seek = QSlider(Qt.Orientation.Horizontal)
        self._seek.setRange(0, 0)
        self._seek.sliderMoved.connect(self._player.setPosition)
        bottom.addWidget(self._seek)

        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(10)

        self._back10 = QPushButton("⟲ 10")
        self._back10.setProperty("icon", True)
        self._back10.setMinimumWidth(54)
        self._back10.clicked.connect(lambda: self._skip(-10_000))
        ctrl_row.addWidget(self._back10)

        self._play_btn = QPushButton("▶")
        self._play_btn.setProperty("accent", True)
        self._play_btn.setFixedSize(54, 40)
        self._play_btn.clicked.connect(self._toggle_play)
        ctrl_row.addWidget(self._play_btn)

        self._fwd10 = QPushButton("10 ⟳")
        self._fwd10.setProperty("icon", True)
        self._fwd10.setMinimumWidth(54)
        self._fwd10.clicked.connect(lambda: self._skip(10_000))
        ctrl_row.addWidget(self._fwd10)

        self._time = QLabel("0:00 / 0:00")
        self._time.setObjectName("muted")
        ctrl_row.addWidget(self._time)

        ctrl_row.addStretch(1)

        self._quality_box = QComboBox()
        self._quality_box.currentIndexChanged.connect(self._on_quality_changed)
        ctrl_row.addWidget(self._quality_box)

        self._dub_box = QComboBox()
        self._dub_box.setMinimumWidth(140)
        self._dub_box.setToolTip("Dub track")
        self._dub_box.currentIndexChanged.connect(self._on_dub_changed)
        ctrl_row.addWidget(self._dub_box)

        self._ep_box = QComboBox()
        self._ep_box.setMinimumWidth(120)
        self._ep_box.setToolTip("Episode")
        self._ep_box.currentIndexChanged.connect(self._on_episode_changed)
        ctrl_row.addWidget(self._ep_box)

        self._prev_btn = QPushButton("⏮")
        self._prev_btn.setProperty("icon", True)
        self._prev_btn.setToolTip("Previous episode")
        self._prev_btn.clicked.connect(lambda: self._step_episode(-1))
        ctrl_row.addWidget(self._prev_btn)

        self._next_btn = QPushButton("⏭")
        self._next_btn.setProperty("icon", True)
        self._next_btn.setToolTip("Next episode")
        self._next_btn.clicked.connect(lambda: self._step_episode(1))
        ctrl_row.addWidget(self._next_btn)

        vol_label = QLabel("🔊")
        ctrl_row.addWidget(vol_label)
        self._vol = QSlider(Qt.Orientation.Horizontal)
        self._vol.setFixedWidth(110)
        self._vol.setRange(0, 100)
        self._vol.setValue(80)
        self._vol.valueChanged.connect(lambda v: self._audio.setVolume(v / 100))
        ctrl_row.addWidget(self._vol)

        bottom.addLayout(ctrl_row)
        wrap.addLayout(bottom)

    # ── public ────────────────────────────────────────────────────────────

    def play(self, anime: Anime, episode: Episode, playlist: list[Episode] | None = None) -> None:
        self._anime = anime
        self._playlist = list(playlist) if playlist else [episode]
        self._episode = episode
        self._title_label.setText(anime.title)
        self._ep_label.setText(
            f"Episode {episode.number}"
            + (f" · {episode.dub}" if episode.dub else "")
        )
        self._rebuild_dub_box()
        self._rebuild_episode_box()
        self._status.setText(f"Resolving {episode.player_name or 'player'}…")
        self._root.setCurrentWidget(self._status_frame)
        self._player.stop()

        resolver = resolve_for(episode.embed_url)
        if resolver is None:
            self._status.setText(f"No resolver for {episode.embed_url}")
            self.error.emit("No resolver for this embed URL.")
            return

        run_async(
            resolver.resolve(episode.embed_url),
            on_done=self._on_sources,
            on_error=self._on_resolve_error,
        )

    def _on_resolve_error(self, exc: BaseException) -> None:
        msg = str(exc) or exc.__class__.__name__
        self._status.setText(f"Resolve failed: {msg}")
        self._root.setCurrentWidget(self._status_frame)
        self.error.emit(f"Resolve failed: {msg}")

    def stop(self) -> None:
        self._save_progress()
        self._player.stop()
        self._save_timer.stop()

    # ── source loading ────────────────────────────────────────────────────

    def _on_sources(self, sources: list[VideoSource]) -> None:
        if not sources:
            self._status.setText("No playable streams found.")
            self.error.emit("No playable streams found.")
            return
        self._sources = sources
        self._quality_box.blockSignals(True)
        self._quality_box.clear()
        for s in sources:
            self._quality_box.addItem(s.quality)
        self._quality_box.blockSignals(False)

        cfg = Config.load()
        idx = 0  # sources are highest-first; default is best available
        if cfg.preferred_quality and cfg.preferred_quality.lower() not in {"best", "max", "auto", ""}:
            try:
                target = int(cfg.preferred_quality.rstrip("p"))
                idx = min(range(len(sources)), key=lambda i: abs(sources[i].height - target))
            except Exception:
                idx = 0
        self._quality_box.setCurrentIndex(idx)
        self._load_source(sources[idx])

    def _on_quality_changed(self, index: int) -> None:
        if 0 <= index < len(self._sources):
            pos = self._player.position()
            self._load_source(self._sources[index])
            QTimer.singleShot(400, lambda: self._player.setPosition(pos))

    def _load_source(self, src: VideoSource) -> None:
        self._player.setSource(QUrl(src.url))
        self._player.play()
        self._root.setCurrentWidget(self._overlay)
        self._save_timer.start()
        self._wake_overlay()

    # ── controls ──────────────────────────────────────────────────────────

    def _toggle_play(self) -> None:
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            self._player.play()

    def _toggle_fullscreen(self) -> None:
        win = self.window()
        if win.isFullScreen():
            win.showNormal()
        else:
            win.showFullScreen()

    def _skip(self, delta_ms: int) -> None:
        self._player.setPosition(max(0, self._player.position() + delta_ms))

    # ── overlay autohide ──────────────────────────────────────────────────

    def _wake_overlay(self) -> None:
        self._overlay.show()
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self._hide_timer.start(2500)

    def _hide_overlay(self) -> None:
        # Only auto-hide in fullscreen; otherwise controls are always visible.
        if not self.window().isFullScreen():
            return
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._overlay.hide()
            self.setCursor(Qt.CursorShape.BlankCursor)

    def mouseMoveEvent(self, e):  # noqa: N802
        self._wake_overlay()
        super().mouseMoveEvent(e)

    def keyPressEvent(self, e: QKeyEvent):  # noqa: N802
        k = e.key()
        if k == Qt.Key.Key_Space:
            self._toggle_play()
        elif k == Qt.Key.Key_Right:
            self._skip(60_000 if e.modifiers() & Qt.KeyboardModifier.ShiftModifier else 10_000)
        elif k == Qt.Key.Key_Left:
            self._skip(-60_000 if e.modifiers() & Qt.KeyboardModifier.ShiftModifier else -10_000)
        elif k in (Qt.Key.Key_F,):
            self._toggle_fullscreen()
        elif k == Qt.Key.Key_Escape and self.window().isFullScreen():
            self.window().showNormal()
        elif k == Qt.Key.Key_Up:
            self._vol.setValue(min(100, self._vol.value() + 5))
        elif k == Qt.Key.Key_Down:
            self._vol.setValue(max(0, self._vol.value() - 5))
        elif k == Qt.Key.Key_M:
            self._audio.setMuted(not self._audio.isMuted())
        else:
            super().keyPressEvent(e)
        self._wake_overlay()

    # ── slots ─────────────────────────────────────────────────────────────

    def _on_state(self, state) -> None:
        self._play_btn.setText("❚❚" if state == QMediaPlayer.PlaybackState.PlayingState else "▶")
        if state == QMediaPlayer.PlaybackState.PausedState:
            self._wake_overlay()
            self._hide_timer.stop()

    def _on_position(self, pos: int) -> None:
        self._seek.blockSignals(True)
        self._seek.setValue(pos)
        self._seek.blockSignals(False)
        self._time.setText(f"{_fmt(pos)} / {_fmt(self._player.duration())}")

    def _on_duration(self, dur: int) -> None:
        self._seek.setRange(0, dur)

    def _on_error(self, _err, msg: str = "") -> None:
        if msg:
            self._status.setText(f"Playback error: {msg}")
            self.error.emit(f"Playback error: {msg}")

    def _save_progress(self) -> None:
        if not (self._anime and self._episode):
            return
        if self._player.duration() <= 0:
            return
        get_library().record_progress(
            self._anime.provider_id,
            self._anime.url,
            self._episode.number,
            self._player.position() // 1000,
            self._player.duration() // 1000,
        )

    def resizeEvent(self, e):  # noqa: N802
        super().resizeEvent(e)
        # keep overlay covering the video stack
        self._overlay.setGeometry(self.rect())

    def hideEvent(self, e):  # noqa: N802
        # Stop playback whenever the player page is hidden so audio does
        # not keep running in the background after navigation.
        self._save_progress()
        self._player.stop()
        self._save_timer.stop()
        super().hideEvent(e)

    # ── episode / dub switching ───────────────────────────────────────────

    def _current_dub(self) -> str:
        return (self._episode.dub if self._episode and self._episode.dub else "")

    def _episodes_for_dub(self, dub: str) -> list[Episode]:
        if not self._playlist:
            return []
        filtered = [e for e in self._playlist if (e.dub or "") == dub]
        # dedupe by number, preserving order
        seen: set[int] = set()
        out: list[Episode] = []
        for e in filtered:
            if e.number in seen:
                continue
            seen.add(e.number)
            out.append(e)
        out.sort(key=lambda e: e.number)
        return out

    def _rebuild_dub_box(self) -> None:
        dubs: list[str] = []
        for e in self._playlist:
            d = e.dub or ""
            if d not in dubs:
                dubs.append(d)
        self._dub_box.blockSignals(True)
        self._dub_box.clear()
        for d in dubs:
            self._dub_box.addItem(d or "Default", d)
        current = self._current_dub()
        for i in range(self._dub_box.count()):
            if self._dub_box.itemData(i) == current:
                self._dub_box.setCurrentIndex(i)
                break
        self._dub_box.setVisible(len(dubs) > 1)
        self._dub_box.blockSignals(False)

    def _rebuild_episode_box(self) -> None:
        eps = self._episodes_for_dub(self._current_dub())
        self._ep_box.blockSignals(True)
        self._ep_box.clear()
        idx = 0
        for i, e in enumerate(eps):
            self._ep_box.addItem(f"Episode {e.number}", e.number)
            if self._episode and e.number == self._episode.number:
                idx = i
        if eps:
            self._ep_box.setCurrentIndex(idx)
        self._ep_box.setEnabled(len(eps) > 1)
        self._prev_btn.setEnabled(len(eps) > 1)
        self._next_btn.setEnabled(len(eps) > 1)
        self._ep_box.blockSignals(False)

    def _on_dub_changed(self, _index: int) -> None:
        if not self._anime:
            return
        new_dub = self._dub_box.currentData() or ""
        eps = self._episodes_for_dub(new_dub)
        if not eps:
            return
        # Pick same number if available, else first.
        target = next(
            (e for e in eps if self._episode and e.number == self._episode.number),
            eps[0],
        )
        self.play(self._anime, target, self._playlist)

    def _on_episode_changed(self, _index: int) -> None:
        if not self._anime:
            return
        num = self._ep_box.currentData()
        if num is None:
            return
        eps = self._episodes_for_dub(self._current_dub())
        target = next((e for e in eps if e.number == num), None)
        if target and (not self._episode or target.number != self._episode.number):
            self.play(self._anime, target, self._playlist)

    def _step_episode(self, delta: int) -> None:
        if not self._anime or not self._episode:
            return
        eps = self._episodes_for_dub(self._current_dub())
        try:
            i = next(idx for idx, e in enumerate(eps) if e.number == self._episode.number)
        except StopIteration:
            return
        ni = i + delta
        if 0 <= ni < len(eps):
            self.play(self._anime, eps[ni], self._playlist)
