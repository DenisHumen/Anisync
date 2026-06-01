"""Downloads page — grouped by anime with poster previews.

Each anime is one expandable :class:`AnimeDownloadGroup` that owns its
episode rows. Aggregate progress (avg of running tasks) is shown in the
group header. Posters are looked up from the SQLite ``anime_cache`` and
loaded asynchronously.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from anisync.core.downloader import get_manager
from anisync.core.library import get_library
from anisync.core.models import DownloadStatus, DownloadTask
from anisync.ui.glass import apply_shadow
from anisync.ui.widgets.poster_loader import PosterLoader


_STATUS_LABEL = {
    DownloadStatus.QUEUED:    "Queued",
    DownloadStatus.RUNNING:   "Downloading",
    DownloadStatus.PAUSED:    "Paused",
    DownloadStatus.COMPLETED: "Completed",
    DownloadStatus.FAILED:    "Failed",
    DownloadStatus.CANCELED:  "Canceled",
}


def _fmt_speed(bps: float) -> str:
    if bps <= 0:
        return ""
    if bps < 1024 * 1024:
        return f"{bps / 1024:,.0f} KB/s"
    return f"{bps / (1024 * 1024):.1f} MB/s"


class DownloadsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._groups: dict[tuple[str, str], AnimeDownloadGroup] = {}
        self._row_index: dict[int, EpisodeRow] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 24, 36, 24)
        root.setSpacing(16)

        # ── header ──
        header = QHBoxLayout()
        title = QLabel("Downloads")
        title.setObjectName("h1")
        header.addWidget(title)
        header.addStretch(1)

        self._summary = QLabel("")
        self._summary.setObjectName("muted")
        header.addWidget(self._summary)

        clean = QPushButton("Clean completed")
        clean.setProperty("ghost", True)
        clean.clicked.connect(self._clean_completed)
        header.addWidget(clean)

        refresh = QPushButton("Refresh")
        refresh.setProperty("ghost", True)
        refresh.clicked.connect(self.refresh)
        header.addWidget(refresh)
        root.addLayout(header)

        # ── scroll area ──
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        root.addWidget(self._scroll, 1)

        self._container = QWidget()
        self._vbox = QVBoxLayout(self._container)
        self._vbox.setSpacing(14)
        self._vbox.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._scroll.setWidget(self._container)

        # ── wire to manager ──
        mgr = get_manager()
        mgr.signals.enqueued.connect(self._on_enqueued)
        mgr.signals.started.connect(self._refresh_row)
        mgr.signals.progress.connect(self._on_progress)
        mgr.signals.completed.connect(self._on_done)
        mgr.signals.failed.connect(lambda tid, _m: self._refresh_row(tid))
        mgr.signals.canceled.connect(self._refresh_row)

        self.refresh()

    # ── refresh ───────────────────────────────────────────────────────────

    def refresh(self) -> None:
        self._clear()
        tasks = get_library().list_downloads()
        # group by (provider_id, anime_url)
        groups: dict[tuple[str, str], list[DownloadTask]] = defaultdict(list)
        for t in tasks:
            groups[(t.provider_id, t.anime_url)].append(t)
        for key, items in groups.items():
            self._add_group(key, items)
        self._update_summary()

    def _clear(self) -> None:
        while self._vbox.count():
            item = self._vbox.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._groups.clear()
        self._row_index.clear()

    def _add_group(self, key: tuple[str, str], tasks: list[DownloadTask]) -> AnimeDownloadGroup:
        first = tasks[0]
        cached = get_library().get_cached(first.provider_id, first.anime_url)
        poster = cached.poster_url if cached else None
        grp = AnimeDownloadGroup(first.anime_title, first.provider_id, poster)
        for t in tasks:
            row = grp.add_episode(t)
            self._row_index[t.id] = row
        self._groups[key] = grp
        self._vbox.insertWidget(0, grp)
        return grp

    # ── manager signals ───────────────────────────────────────────────────

    def _on_enqueued(self, task: DownloadTask) -> None:
        key = (task.provider_id, task.anime_url)
        grp = self._groups.get(key)
        if grp is None:
            grp = self._add_group(key, [task])
            return
        row = grp.add_episode(task)
        self._row_index[task.id] = row
        self._update_summary()

    def _on_progress(self, tid: int, pct: float, speed: float) -> None:
        row = self._row_index.get(tid)
        if row:
            row.set_progress(pct, speed)
            row.group.recompute()
        self._update_summary()

    def _on_done(self, tid: int) -> None:
        self._refresh_row(tid)
        self._update_summary()

    def _refresh_row(self, tid: int) -> None:
        for t in get_library().list_downloads():
            if t.id == tid:
                row = self._row_index.get(tid)
                if row:
                    row.apply_task(t)
                    row.group.recompute()
                break

    def _update_summary(self) -> None:
        total = sum(len(g.rows) for g in self._groups.values())
        running = sum(
            1 for g in self._groups.values()
            for r in g.rows
            if r.task.status == DownloadStatus.RUNNING
        )
        completed = sum(
            1 for g in self._groups.values()
            for r in g.rows
            if r.task.status == DownloadStatus.COMPLETED
        )
        self._summary.setText(
            f"{total} total · {running} running · {completed} completed"
        )

    def _clean_completed(self) -> None:
        lib = get_library()
        for t in lib.list_downloads():
            if t.status in (DownloadStatus.COMPLETED, DownloadStatus.CANCELED):
                lib.delete_download(t.id)
        self.refresh()


# ─── group widget ─────────────────────────────────────────────────────────


class AnimeDownloadGroup(QFrame):
    def __init__(self, anime_title: str, provider_id: str, poster_url: str | None) -> None:
        super().__init__()
        self.setObjectName("card")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        apply_shadow(self, blur=28, y_offset=6, alpha=80)

        self.rows: list[EpisodeRow] = []

        v = QVBoxLayout(self)
        v.setContentsMargins(16, 14, 16, 14)
        v.setSpacing(10)

        # header row: poster + title + aggregate progress
        top = QHBoxLayout()
        top.setSpacing(14)

        self._poster = QLabel()
        self._poster.setFixedSize(70, 96)
        self._poster.setStyleSheet("background:#0A0A12; border-radius:8px;")
        self._poster.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top.addWidget(self._poster)

        meta_col = QVBoxLayout()
        meta_col.setSpacing(4)
        title = QLabel(anime_title)
        title.setObjectName("cardTitle")
        title.setStyleSheet("font-size:15px; font-weight:700;")
        meta_col.addWidget(title)

        src = QLabel(f"Source: {provider_id}")
        src.setObjectName("dim")
        meta_col.addWidget(src)

        self._agg_label = QLabel("0%")
        self._agg_label.setObjectName("muted")
        meta_col.addWidget(self._agg_label)

        self._agg_bar = QProgressBar()
        self._agg_bar.setRange(0, 1000)
        meta_col.addWidget(self._agg_bar)

        top.addLayout(meta_col, 1)
        v.addLayout(top)

        # episode list container
        self._eps_box = QVBoxLayout()
        self._eps_box.setSpacing(6)
        v.addLayout(self._eps_box)

        self._loader = PosterLoader(poster_url)
        self._loader.loaded.connect(self._apply_poster)
        self._loader.start()

    def add_episode(self, task: DownloadTask) -> EpisodeRow:
        row = EpisodeRow(task, self)
        self.rows.append(row)
        self._eps_box.addWidget(row)
        self.recompute()
        return row

    def recompute(self) -> None:
        if not self.rows:
            return
        total = sum(r.task.progress for r in self.rows) / len(self.rows)
        self._agg_bar.setValue(int(total * 1000))
        running = sum(1 for r in self.rows if r.task.status == DownloadStatus.RUNNING)
        done = sum(1 for r in self.rows if r.task.status == DownloadStatus.COMPLETED)
        self._agg_label.setText(
            f"{total * 100:.0f}%   ·   {done}/{len(self.rows)} done"
            + (f"   ·   {running} running" if running else "")
        )

    def _apply_poster(self, data: bytes) -> None:
        if not data:
            return
        pix = QPixmap()
        if pix.loadFromData(data):
            self._poster.setPixmap(
                pix.scaled(
                    self._poster.size(),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )


# ─── per-episode row ──────────────────────────────────────────────────────


class EpisodeRow(QFrame):
    def __init__(self, task: DownloadTask, group: AnimeDownloadGroup) -> None:
        super().__init__()
        self.task = task
        self.group = group
        self.setStyleSheet(
            "QFrame {"
            "  background: rgba(255,255,255,12);"
            "  border: 1px solid rgba(255,255,255,20);"
            "  border-radius: 10px;"
            "}"
        )

        h = QHBoxLayout(self)
        h.setContentsMargins(12, 8, 12, 8)
        h.setSpacing(10)

        self._title = QLabel(f"Episode {task.episode_number} · {task.quality}")
        self._title.setStyleSheet("font-weight:600;")
        h.addWidget(self._title)

        h.addStretch(1)

        self._status = QLabel(_STATUS_LABEL[task.status])
        self._status.setStyleSheet(
            "color:#9A9AA5; font-size:12px; background:transparent; border:none;"
        )
        h.addWidget(self._status)

        self._bar = QProgressBar()
        self._bar.setFixedWidth(220)
        self._bar.setRange(0, 1000)
        self._bar.setValue(int(task.progress * 1000))
        h.addWidget(self._bar)

        self._pct = QLabel(f"{task.progress * 100:.0f}%")
        self._pct.setStyleSheet(
            "color:#9A9AA5; font-size:12px; background:transparent; border:none;"
        )
        self._pct.setFixedWidth(48)
        self._pct.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        h.addWidget(self._pct)

        self._open_btn = QPushButton("Open")
        self._open_btn.setProperty("ghost", True)
        self._open_btn.clicked.connect(self._open_file)
        h.addWidget(self._open_btn)

        self._retry_btn = QPushButton("Retry")
        self._retry_btn.setProperty("ghost", True)
        self._retry_btn.clicked.connect(self._retry)
        h.addWidget(self._retry_btn)

        self._remove_btn = QPushButton("Remove")
        self._remove_btn.setProperty("ghost", True)
        self._remove_btn.clicked.connect(self._remove)
        h.addWidget(self._remove_btn)

        self._sync_buttons()

    def _sync_buttons(self) -> None:
        is_failed = self.task.status in (DownloadStatus.FAILED, DownloadStatus.CANCELED)
        is_done = self.task.status == DownloadStatus.COMPLETED
        self._retry_btn.setVisible(is_failed)
        self._remove_btn.setVisible(is_failed or is_done)
        self._open_btn.setVisible(is_done)

    def set_progress(self, pct: float, speed: float) -> None:
        self.task.progress = pct
        self.task.status = DownloadStatus.RUNNING
        self._bar.setValue(int(pct * 1000))
        self._pct.setText(f"{pct * 100:.0f}%")
        s = _fmt_speed(speed)
        self._status.setText(f"Downloading · {s}" if s else "Downloading")
        self._sync_buttons()

    def apply_task(self, task: DownloadTask) -> None:
        self.task = task
        self._bar.setValue(int(task.progress * 1000))
        self._pct.setText(f"{task.progress * 100:.0f}%")
        label = _STATUS_LABEL[task.status]
        if task.status == DownloadStatus.FAILED and task.error:
            label = f"Failed: {task.error.splitlines()[0][:80]}"
        self._status.setText(label)
        self._sync_buttons()

    def _retry(self) -> None:
        from anisync.core.models import Episode
        from anisync.utils.async_runner import run_async

        old = self.task
        lib = get_library()
        lib.delete_download(old.id)
        ep = Episode(
            provider_id=old.provider_id,
            anime_url=old.anime_url,
            number=old.episode_number,
            title=None,
            embed_url=old.embed_url,
        )
        mgr = get_manager()
        run_async(mgr.enqueue(ep, old.anime_title, quality=old.quality))
        # Page will pick up the new task via the enqueued signal.
        parent_page = self._find_page()
        if parent_page is not None:
            parent_page.refresh()

    def _remove(self) -> None:
        get_library().delete_download(self.task.id)
        page = self._find_page()
        if page is not None:
            page.refresh()

    def _find_page(self) -> "DownloadsPage | None":
        w = self.parent()
        while w is not None:
            if isinstance(w, DownloadsPage):
                return w
            w = w.parent()
        return None

    def _open_file(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        p = Path(self.task.file_path)
        target = p if p.exists() else p.parent
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))
