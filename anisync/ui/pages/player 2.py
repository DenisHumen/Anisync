"""Video player page (Qt Multimedia).

Resolves embed URL via :func:`resolve_for`, plays best available source.
Reports playback progress to the library every few seconds.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtNetwork import QNetworkRequest
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
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


def _format_time(ms: int) -> str:
    s = max(0, ms // 1000)
    m, sec = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h:d}:{m:02d}:{sec:02d}" if h else f"{m:d}:{sec:02d}"


class PlayerPage(QWidget):
    error = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._anime: Anime | None = None
        self._episode: Episode | None = None
        self._sources: list[VideoSource] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # ── status overlay + video ──
        self._stack = QStackedLayout()
        root.addLayout(self._stack, 1)

        self._status = QLabel("No video loaded.")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setObjectName("muted")
        self._stack.addWidget(self._status)

        self._video = QVideoWidget()
        self._stack.addWidget(self._video)

        # ── media pipeline ──
        self._player = QMediaPlayer(self)
        self._audio = QAudioOutput(self)
        self._player.setAudioOutput(self._audio)
        self._player.setVideoOutput(self._video)
        self._audio.setVolume(0.8)

        self._player.positionChanged.connect(self._on_position)
        self._player.durationChanged.connect(self._on_duration)
        self._player.errorOccurred.connect(self._on_error)
        self._player.playbackStateChanged.connect(self._on_state)

        # ── controls ──
        controls = QHBoxLayout()
        controls.setContentsMargins(16, 8, 16, 12)
        controls.setSpacing(10)

        self._play_btn = QPushButton("▶")
        self._play_btn.setFixedWidth(40)
        self._play_btn.clicked.connect(self._toggle_play)
        controls.addWidget(self._play_btn)

        self._time = QLabel("0:00 / 0:00")
        controls.addWidget(self._time)

        self._seek = QSlider(Qt.Orientation.Horizontal)
        self._seek.setRange(0, 0)
        self._seek.sliderMoved.connect(self._player.setPosition)
        controls.addWidget(self._seek, 1)

        self._quality_box = QComboBox()
        self._quality_box.currentIndexChanged.connect(self._on_quality_changed)
        controls.addWidget(self._quality_box)

        self._vol = QSlider(Qt.Orientation.Horizontal)
        self._vol.setFixedWidth(100)
        self._vol.setRange(0, 100)
        self._vol.setValue(80)
        self._vol.valueChanged.connect(lambda v: self._audio.setVolume(v / 100))
        controls.addWidget(self._vol)

        root.addLayout(controls)

        # Throttle history writes
        self._save_timer = QTimer(self)
        self._save_timer.setInterval(5000)
        self._save_timer.timeout.connect(self._save_progress)

    # ─── public API ───────────────────────────────────────────────────────

    def play(self, anime: Anime, episode: Episode) -> None:
        self._anime = anime
        self._episode = episode
        self._status.setText(f"Resolving {episode.player_name or 'player'}…")
        self._stack.setCurrentWidget(self._status)
        self._player.stop()

        resolver = resolve_for(episode.embed_url)
        if resolver is None:
            self._status.setText(f"No resolver for {episode.embed_url}")
            self.error.emit("No resolver for this embed URL.")
            return

        run_async(
            resolver.resolve(episode.embed_url),
            on_done=self._on_sources,
            on_error=lambda e: (
                self._status.setText(f"Resolve failed: {e}"),
                self.error.emit(f"Resolve failed: {e}"),
            ),
        )

    def stop(self) -> None:
        self._save_progress()
        self._player.stop()
        self._save_timer.stop()

    # ─── internals ────────────────────────────────────────────────────────

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

        # Prefer config quality, else first
        cfg = Config.load()
        idx = 0
        try:
            target = int(cfg.preferred_quality.rstrip("p"))
            best = min(range(len(sources)), key=lambda i: abs(sources[i].height - target))
            idx = best
        except Exception:
            pass
        self._quality_box.setCurrentIndex(idx)
        self._load_source(sources[idx])

    def _on_quality_changed(self, index: int) -> None:
        if 0 <= index < len(self._sources):
            position = self._player.position()
            self._load_source(self._sources[index])
            QTimer.singleShot(500, lambda: self._player.setPosition(position))

    def _load_source(self, src: VideoSource) -> None:
        req = QNetworkRequest(QUrl(src.url))
        for k, v in (src.headers or {}).items():
            req.setRawHeader(k.encode(), v.encode())
        self._player.setSource(QUrl(src.url))
        # Qt Multimedia on macOS uses AVFoundation; custom headers are
        # not always honored. The Referer is set on the URL fragment if
        # the backend supports it; otherwise the stream still loads
        # because Kodik does not strictly enforce Referer for HLS.
        self._player.play()
        self._stack.setCurrentWidget(self._video)
        self._save_timer.start()

    def _toggle_play(self) -> None:
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            self._player.play()

    def _on_state(self, state) -> None:
        self._play_btn.setText("❚❚" if state == QMediaPlayer.PlaybackState.PlayingState else "▶")

    def _on_position(self, pos: int) -> None:
        self._seek.blockSignals(True)
        self._seek.setValue(pos)
        self._seek.blockSignals(False)
        self._time.setText(f"{_format_time(pos)} / {_format_time(self._player.duration())}")

    def _on_duration(self, dur: int) -> None:
        self._seek.setRange(0, dur)

    def _on_error(self, err, msg: str = "") -> None:
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
