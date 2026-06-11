"""Plex / Jellyfin-style video player powered by libmpv.

We embed mpv into a native QWidget via the `wid` option, which gives us
mpv's battle-tested decoding pipeline (HLS, DASH, custom headers, every
codec under the sun, hardware acceleration) while keeping a Qt overlay
on top for our own controls.

Controls overlay fades out after 2.5 s of mouse inactivity in fullscreen
(Plex-style) and stays visible in windowed mode. Keyboard shortcuts:
Space (play/pause), ← / → (seek 10 s), Shift+← / Shift+→ (seek 60 s),
F (fullscreen), Esc (exit fullscreen), ↑ / ↓ (volume), M (mute).
"""
from __future__ import annotations

import sys
from typing import Any

from PySide6.QtCore import QPoint, QSize, QTimer, Qt, Signal
from PySide6.QtGui import QKeyEvent, QOpenGLContext
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
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
from anisync.ui.widgets.icons import (
    back_icon,
    fullscreen_icon,
    next_icon,
    pause_icon,
    play_icon,
    prev_icon,
    skip_icon,
    volume_pixmap,
)
from anisync.utils.async_runner import run_async
from anisync.utils.mpv_loader import load_mpv


def _fmt(seconds: float | int | None) -> str:
    s = int(max(0, seconds or 0))
    m, sec = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h:d}:{m:02d}:{sec:02d}" if h else f"{m:d}:{sec:02d}"


def _gl_get_proc_address(_ctx, name):
    """libmpv calls this to resolve OpenGL function pointers via Qt.

    Runs on the GL thread with a current QOpenGLContext.
    """
    glctx = QOpenGLContext.currentContext()
    if glctx is None:
        return 0
    if isinstance(name, bytes):
        name = name.decode("utf-8")
    addr = glctx.getProcAddress(name)
    try:
        return int(addr)
    except Exception:
        return 0


class _MpvVideoWidget(QOpenGLWidget):
    """QOpenGLWidget that hosts mpv's render API.

    mpv renders straight into our framebuffer, so the video is properly
    embedded inside the Qt window instead of opening a detached cocoa
    window (which is what `wid` embedding does on macOS).
    """

    # Emitted from the mpv render thread when a new frame is ready.
    frame_ready = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background:#000;")
        self.setMouseTracking(True)
        self._mpv: Any = None
        self._render_ctx: Any = None
        self._get_proc_fn: Any = None
        self._mpv_module: Any = None
        self.frame_ready.connect(self.update, Qt.ConnectionType.QueuedConnection)

    def attach_mpv(self, mpv_module: Any, mpv_player: Any) -> None:
        """Bind an mpv player to this widget. Must be called before showing."""
        self._mpv_module = mpv_module
        self._mpv = mpv_player

    def initializeGL(self) -> None:  # noqa: N802
        if self._mpv is None or self._mpv_module is None:
            return
        mpv = self._mpv_module
        # Keep the callback alive on self — it is invoked from C.
        self._get_proc_fn = mpv.MpvGlGetProcAddressFn(_gl_get_proc_address)
        try:
            self._render_ctx = mpv.MpvRenderContext(
                self._mpv,
                "opengl",
                opengl_init_params={"get_proc_address": self._get_proc_fn},
            )
        except Exception as exc:
            # Bubble up a visible error rather than silently showing black.
            print(f"[player] MpvRenderContext init failed: {exc}", file=sys.stderr)
            return
        # mpv calls this from its render thread → marshal via queued signal.
        self._render_ctx.update_cb = self.frame_ready.emit

    def paintGL(self) -> None:  # noqa: N802
        if self._render_ctx is None:
            return
        ratio = self.devicePixelRatioF()
        w = max(1, int(self.width() * ratio))
        h = max(1, int(self.height() * ratio))
        try:
            self._render_ctx.render(
                flip_y=True,
                opengl_fbo={"w": w, "h": h, "fbo": int(self.defaultFramebufferObject())},
            )
        except Exception as exc:
            print(f"[player] render failed: {exc}", file=sys.stderr)

    def shutdown(self) -> None:
        if self._render_ctx is not None:
            try:
                self._render_ctx.update_cb = None
                self._render_ctx.free()
            except Exception:
                pass
            self._render_ctx = None


class PlayerPage(QWidget):
    error = Signal(str)
    back_requested = Signal()
    # Internal signals used to marshal mpv property updates from the mpv
    # event thread onto the Qt main thread (signals are auto-queued across
    # threads when receiver lives on another thread).
    _sig_position = Signal(float)
    _sig_duration = Signal(float)
    _sig_pause = Signal(bool)
    _sig_eof = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._anime: Anime | None = None
        self._episode: Episode | None = None
        self._playlist: list[Episode] = []
        self._sources: list[VideoSource] = []
        self._duration: float = 0.0
        self._position: float = 0.0
        self._paused: bool = False
        self._mpv_failed: str | None = None
        self._last_mouse = QPoint(0, 0)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)

        # ── stacked: status placeholder + video ──
        root = QStackedLayout(self)
        root.setStackingMode(QStackedLayout.StackingMode.StackAll)
        root.setContentsMargins(0, 0, 0, 0)
        self._root = root

        self._video = _MpvVideoWidget()
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
        self._status_frame.setVisible(True)

        # ── overlay (top bar + bottom bar) ──
        self._overlay = QFrame(self)
        self._overlay.setObjectName("playerOverlay")
        self._overlay.setMouseTracking(True)
        self._overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self._build_overlay()
        root.addWidget(self._overlay)
        self._status_frame.setVisible(True)  # initial placeholder

        # ── timers ──
        self._save_timer = QTimer(self)
        self._save_timer.setInterval(5000)
        self._save_timer.timeout.connect(self._save_progress)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._hide_overlay)

        # marshal mpv-thread events onto the main thread
        self._sig_position.connect(self._apply_position, Qt.ConnectionType.QueuedConnection)
        self._sig_duration.connect(self._apply_duration, Qt.ConnectionType.QueuedConnection)
        self._sig_pause.connect(self._apply_pause, Qt.ConnectionType.QueuedConnection)
        self._sig_eof.connect(self._on_eof, Qt.ConnectionType.QueuedConnection)

        # mpv is created lazily after the native window id is realised.
        self._mpv: Any = None
        QTimer.singleShot(0, self._init_mpv)

    # ── status helpers ────────────────────────────────────────────────────

    def _show_status(self, text: str) -> None:
        self._status.setText(text)
        self._status_frame.setVisible(True)
        self._status_frame.raise_()
        self._overlay.raise_()

    def _hide_status(self) -> None:
        self._status_frame.setVisible(False)
        self._overlay.raise_()

    # ── mpv setup ─────────────────────────────────────────────────────────

    def _init_mpv(self) -> None:
        if self._mpv is not None:
            return
        try:
            mpv = load_mpv()
        except Exception as exc:
            self._mpv_failed = (
                f"libmpv not available ({exc}). Install with: brew install mpv"
                if sys.platform == "darwin"
                else f"libmpv not available ({exc}). Install the mpv / libmpv package."
            )
            self._show_status(self._mpv_failed)
            return

        # vo=libmpv lets us embed via the render API into a QOpenGLWidget.
        common_opts = dict(
            vo="libmpv",
            ytdl=False,
            osc=False,
            input_default_bindings=False,
            input_vo_keyboard=False,
            keep_open="yes",
            terminal=False,
            volume=80,
        )
        try:
            self._mpv = mpv.MPV(hwdec="auto-safe", **common_opts)
        except Exception:
            try:
                self._mpv = mpv.MPV(**common_opts)
            except Exception as exc2:
                self._mpv_failed = f"mpv init failed: {exc2}"
                self._show_status(self._mpv_failed)
                return

        # Hand the player to the GL widget so it can create the render ctx.
        self._video.attach_mpv(mpv, self._mpv)
        # Force a GL initialisation pass so render ctx exists before play.
        self._video.show()
        self._video.update()

        self._mpv.observe_property("time-pos", self._on_time_pos)
        self._mpv.observe_property("duration", self._on_duration_prop)
        self._mpv.observe_property("pause", self._on_pause_prop)
        self._mpv.observe_property("eof-reached", self._on_eof_prop)

    # ── overlay construction ──────────────────────────────────────────────

    def _build_overlay(self) -> None:
        wrap = QVBoxLayout(self._overlay)
        wrap.setContentsMargins(20, 16, 20, 16)

        top = QHBoxLayout()
        back = QPushButton()
        back.setIcon(back_icon())
        back.setIconSize(QSize(20, 20))
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

        self._fs_btn = QPushButton()
        self._fs_btn.setIcon(fullscreen_icon())
        self._fs_btn.setIconSize(QSize(18, 18))
        self._fs_btn.setProperty("icon", True)
        self._fs_btn.setToolTip("Toggle fullscreen (F)")
        self._fs_btn.clicked.connect(self._toggle_fullscreen)
        top.addWidget(self._fs_btn)

        wrap.addLayout(top)
        wrap.addStretch(1)

        bottom = QVBoxLayout()
        bottom.setSpacing(8)

        self._seek = QSlider(Qt.Orientation.Horizontal)
        self._seek.setRange(0, 0)
        self._seek.sliderMoved.connect(self._on_seek_moved)
        bottom.addWidget(self._seek)

        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(10)

        self._back10 = QPushButton()
        self._back10.setIcon(skip_icon(10, forward=False))
        self._back10.setIconSize(QSize(22, 22))
        self._back10.setProperty("icon", True)
        self._back10.setToolTip("Back 10 s (←)")
        self._back10.clicked.connect(lambda: self._skip(-10))
        ctrl_row.addWidget(self._back10)

        self._icon_play = play_icon()
        self._icon_pause = pause_icon()
        self._play_btn = QPushButton()
        self._play_btn.setIcon(self._icon_play)
        self._play_btn.setIconSize(QSize(18, 18))
        self._play_btn.setProperty("accent", True)
        self._play_btn.setFixedSize(54, 40)
        self._play_btn.setToolTip("Play/Pause (Space)")
        self._play_btn.clicked.connect(self._toggle_play)
        ctrl_row.addWidget(self._play_btn)

        self._fwd10 = QPushButton()
        self._fwd10.setIcon(skip_icon(10, forward=True))
        self._fwd10.setIconSize(QSize(22, 22))
        self._fwd10.setProperty("icon", True)
        self._fwd10.setToolTip("Forward 10 s (→)")
        self._fwd10.clicked.connect(lambda: self._skip(10))
        ctrl_row.addWidget(self._fwd10)

        self._time = QLabel("0:00 / 0:00")
        self._time.setObjectName("muted")
        ctrl_row.addWidget(self._time)

        ctrl_row.addStretch(1)

        self._quality_box = QComboBox()
        self._quality_box.setMaximumWidth(100)
        self._quality_box.currentIndexChanged.connect(self._on_quality_changed)
        ctrl_row.addWidget(self._quality_box)

        self._dub_box = QComboBox()
        # Constrain visible width so long dub names don't push the row off-screen;
        # the popup itself shows full names (popup width set in _rebuild_dub_box).
        self._dub_box.setMinimumWidth(120)
        self._dub_box.setMaximumWidth(200)
        self._dub_box.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self._dub_box.setMinimumContentsLength(10)
        self._dub_box.setToolTip("Dub track")
        self._dub_box.currentIndexChanged.connect(self._on_dub_changed)
        ctrl_row.addWidget(self._dub_box)

        self._ep_box = QComboBox()
        self._ep_box.setMinimumWidth(100)
        self._ep_box.setMaximumWidth(160)
        self._ep_box.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self._ep_box.setMinimumContentsLength(8)
        self._ep_box.setToolTip("Episode")
        self._ep_box.currentIndexChanged.connect(self._on_episode_changed)
        ctrl_row.addWidget(self._ep_box)

        self._prev_btn = QPushButton()
        self._prev_btn.setIcon(prev_icon())
        self._prev_btn.setIconSize(QSize(18, 18))
        self._prev_btn.setProperty("icon", True)
        self._prev_btn.setToolTip("Previous episode")
        self._prev_btn.clicked.connect(lambda: self._step_episode(-1))
        ctrl_row.addWidget(self._prev_btn)

        self._next_btn = QPushButton()
        self._next_btn.setIcon(next_icon())
        self._next_btn.setIconSize(QSize(18, 18))
        self._next_btn.setProperty("icon", True)
        self._next_btn.setToolTip("Next episode")
        self._next_btn.clicked.connect(lambda: self._step_episode(1))
        ctrl_row.addWidget(self._next_btn)

        vol_label = QLabel()
        vol_label.setPixmap(volume_pixmap())
        vol_label.setFixedSize(18, 18)
        ctrl_row.addWidget(vol_label)
        self._vol = QSlider(Qt.Orientation.Horizontal)
        self._vol.setFixedWidth(110)
        self._vol.setRange(0, 100)
        self._vol.setValue(80)
        self._vol.valueChanged.connect(self._on_volume_changed)
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

        if self._mpv is None and self._mpv_failed is None:
            # Try once more — first attempt may have happened before show.
            self._init_mpv()
        if self._mpv_failed:
            self._show_status(self._mpv_failed)
            self.error.emit(self._mpv_failed)
            return

        self._show_status(f"Resolving {episode.player_name or 'player'}…")
        self._stop_playback()

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
        self._show_status(f"Resolve failed: {msg}")
        self.error.emit(f"Resolve failed: {msg}")

    def stop(self) -> None:
        self._save_progress()
        self._stop_playback()
        self._save_timer.stop()

    def _stop_playback(self) -> None:
        if self._mpv is None:
            return
        try:
            self._mpv.command("stop")
        except Exception:
            pass

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
        idx = 0
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
            self._load_source(self._sources[index], resume_at=self._position)

    def _load_source(self, src: VideoSource, resume_at: float = 0.0) -> None:
        if self._mpv is None:
            return
        headers = src.headers or {}
        referer = headers.get("Referer") or headers.get("referer") or ""
        user_agent = headers.get("User-Agent") or headers.get("user-agent") or ""
        other_headers = [
            f"{k}: {v}"
            for k, v in headers.items()
            if k.lower() not in {"referer", "user-agent"}
        ]
        try:
            self._mpv["referrer"] = referer
            if user_agent:
                self._mpv["user-agent"] = user_agent
            self._mpv["http-header-fields"] = ",".join(other_headers) if other_headers else ""
        except Exception:
            pass

        try:
            if resume_at and resume_at > 1:
                self._mpv.command("loadfile", src.url, "replace", f"start={int(resume_at)}")
            else:
                self._mpv.play(src.url)
        except Exception as exc:
            self._show_status(f"Playback error: {exc}")
            self.error.emit(f"Playback error: {exc}")
            return

        self._hide_status()
        self._save_timer.start()
        self._wake_overlay()

    # ── controls ──────────────────────────────────────────────────────────

    def _toggle_play(self) -> None:
        if self._mpv is None:
            return
        try:
            self._mpv.pause = not bool(self._mpv.pause)
        except Exception:
            pass

    def _toggle_fullscreen(self) -> None:
        win = self.window()
        if win.isFullScreen():
            win.showNormal()
        else:
            win.showFullScreen()

    def _skip(self, delta_seconds: int) -> None:
        if self._mpv is None:
            return
        try:
            self._mpv.command("seek", str(delta_seconds), "relative")
        except Exception:
            pass

    def _on_seek_moved(self, value: int) -> None:
        if self._mpv is None:
            return
        try:
            self._mpv.command("seek", str(value), "absolute")
        except Exception:
            pass

    def _on_volume_changed(self, value: int) -> None:
        if self._mpv is None:
            return
        try:
            self._mpv.volume = float(value)
        except Exception:
            pass

    # ── overlay autohide ──────────────────────────────────────────────────

    def _wake_overlay(self) -> None:
        self._overlay.show()
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self._hide_timer.start(2500)

    def _hide_overlay(self) -> None:
        if not self.window().isFullScreen():
            return
        if not self._paused:
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
            self._skip(60 if e.modifiers() & Qt.KeyboardModifier.ShiftModifier else 10)
        elif k == Qt.Key.Key_Left:
            self._skip(-60 if e.modifiers() & Qt.KeyboardModifier.ShiftModifier else -10)
        elif k == Qt.Key.Key_F:
            self._toggle_fullscreen()
        elif k == Qt.Key.Key_Escape and self.window().isFullScreen():
            self.window().showNormal()
        elif k == Qt.Key.Key_Up:
            self._vol.setValue(min(100, self._vol.value() + 5))
        elif k == Qt.Key.Key_Down:
            self._vol.setValue(max(0, self._vol.value() - 5))
        elif k == Qt.Key.Key_M and self._mpv is not None:
            try:
                self._mpv.mute = not bool(self._mpv.mute)
            except Exception:
                pass
        else:
            super().keyPressEvent(e)
        self._wake_overlay()

    # ── mpv property callbacks (mpv thread → marshal to Qt main thread) ──

    def _on_time_pos(self, _name, value):
        if value is None:
            return
        self._sig_position.emit(float(value))

    def _on_duration_prop(self, _name, value):
        if value is None:
            return
        self._sig_duration.emit(float(value))

    def _on_pause_prop(self, _name, value):
        self._sig_pause.emit(bool(value))

    def _on_eof_prop(self, _name, value):
        if value:
            self._sig_eof.emit()

    def _apply_position(self, pos: float) -> None:
        self._position = pos
        self._seek.blockSignals(True)
        self._seek.setValue(int(pos))
        self._seek.blockSignals(False)
        self._time.setText(f"{_fmt(pos)} / {_fmt(self._duration)}")

    def _apply_duration(self, dur: float) -> None:
        self._duration = dur
        self._seek.setRange(0, int(dur))

    def _apply_pause(self, paused: bool) -> None:
        self._paused = paused
        self._play_btn.setIcon(self._icon_play if paused else self._icon_pause)
        if paused:
            self._wake_overlay()
            self._hide_timer.stop()

    # ── progress / lifecycle ──────────────────────────────────────────────

    def _save_progress(self) -> None:
        if not (self._anime and self._episode):
            return
        if self._duration <= 0:
            return
        get_library().record_progress(
            self._anime.provider_id,
            self._anime.url,
            self._episode.number,
            int(self._position),
            int(self._duration),
        )

    def resizeEvent(self, e):  # noqa: N802
        super().resizeEvent(e)
        self._overlay.setGeometry(self.rect())

    def hideEvent(self, e):  # noqa: N802
        self._save_progress()
        self._stop_playback()
        self._save_timer.stop()
        super().hideEvent(e)

    def closeEvent(self, e):  # noqa: N802
        try:
            self._video.shutdown()
        except Exception:
            pass
        if self._mpv is not None:
            try:
                self._mpv.terminate()
            except Exception:
                pass
            self._mpv = None
        super().closeEvent(e)

    # ── episode / dub switching ───────────────────────────────────────────

    def _current_dub(self) -> str:
        return (self._episode.dub if self._episode and self._episode.dub else "")

    def _episodes_for_dub(self, dub: str) -> list[Episode]:
        if not self._playlist:
            return []
        filtered = [e for e in self._playlist if (e.dub or "") == dub]
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
        # Make the popup roomy enough for the longest dub label.
        view = self._dub_box.view()
        fm = self._dub_box.fontMetrics()
        widest = max((fm.horizontalAdvance(d or "Default") for d in dubs), default=160)
        view.setMinimumWidth(min(widest + 48, 360))
        self._dub_box.blockSignals(False)

    def _rebuild_episode_box(self) -> None:
        eps = self._episodes_for_dub(self._current_dub())
        self._ep_box.blockSignals(True)
        self._ep_box.clear()
        idx = 0
        for i, e in enumerate(eps):
            self._ep_box.addItem(f"Ep {e.number}", e.number)
            if self._episode and e.number == self._episode.number:
                idx = i
        if eps:
            self._ep_box.setCurrentIndex(idx)
        self._ep_box.setEnabled(len(eps) > 1)
        self._prev_btn.setEnabled(len(eps) > 1)
        self._next_btn.setEnabled(len(eps) > 1)
        # Wide popup so users can scan episode numbers comfortably.
        self._ep_box.view().setMinimumWidth(160)
        self._ep_box.blockSignals(False)

    def _on_dub_changed(self, _index: int) -> None:
        if not self._anime:
            return
        new_dub = self._dub_box.currentData() or ""
        eps = self._episodes_for_dub(new_dub)
        if not eps:
            return
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

    def _on_eof(self) -> None:
        # Honour the "autoplay next episode" preference; when disabled we
        # simply stop at the end of the current episode.
        if Config.load().autoplay_next:
            self._step_episode(1)

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
