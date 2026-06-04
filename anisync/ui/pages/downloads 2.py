"""Downloads queue page."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from anisync.core.downloader import get_manager
from anisync.core.library import get_library
from anisync.core.models import DownloadStatus, DownloadTask


class DownloadsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._rows: dict[int, _DownloadRow] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 24, 32, 24)
        root.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel("Downloads")
        title.setObjectName("h1")
        header.addWidget(title)
        header.addStretch(1)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        header.addWidget(refresh)
        root.addLayout(header)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        root.addWidget(self._scroll, 1)

        self._container = QWidget()
        self._vbox = QVBoxLayout(self._container)
        self._vbox.setSpacing(10)
        self._vbox.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._scroll.setWidget(self._container)

        mgr = get_manager()
        mgr.signals.enqueued.connect(self._on_enqueued)
        mgr.signals.started.connect(self._refresh_one)
        mgr.signals.progress.connect(self._on_progress)
        mgr.signals.completed.connect(self._refresh_one)
        mgr.signals.failed.connect(lambda tid, _msg: self._refresh_one(tid))
        mgr.signals.canceled.connect(self._refresh_one)

        self.refresh()

    def refresh(self) -> None:
        for row in self._rows.values():
            row.deleteLater()
        self._rows.clear()
        for task in get_library().list_downloads():
            self._add_row(task)

    def _on_enqueued(self, task: DownloadTask) -> None:
        self._add_row(task)

    def _add_row(self, task: DownloadTask) -> None:
        row = _DownloadRow(task)
        self._rows[task.id] = row
        self._vbox.insertWidget(0, row)

    def _on_progress(self, tid: int, pct: float, speed: float) -> None:
        row = self._rows.get(tid)
        if row:
            row.set_progress(pct, speed)

    def _refresh_one(self, tid: int) -> None:
        # Re-read the task from DB to pick up final status/error.
        for t in get_library().list_downloads():
            if t.id == tid and tid in self._rows:
                self._rows[tid].update_status(t)
                return


class _DownloadRow(QFrame):
    def __init__(self, task: DownloadTask) -> None:
        super().__init__()
        self.task = task
        self.setObjectName("card")
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 10, 14, 10)

        top = QHBoxLayout()
        lbl = QLabel(f"{task.anime_title} — Episode {task.episode_number} [{task.quality}]")
        lbl.setObjectName("cardTitle")
        top.addWidget(lbl)
        top.addStretch(1)
        self._status = QLabel(task.status.value)
        self._status.setObjectName("cardMeta")
        top.addWidget(self._status)
        v.addLayout(top)

        self._bar = QProgressBar()
        self._bar.setRange(0, 1000)
        self._bar.setValue(int(task.progress * 1000))
        v.addWidget(self._bar)

        self._meta = QLabel(task.file_path)
        self._meta.setObjectName("cardMeta")
        v.addWidget(self._meta)

    def set_progress(self, pct: float, speed: float) -> None:
        self._bar.setValue(int(pct * 1000))
        kb = speed / 1024
        self._status.setText(f"{pct * 100:.1f}%  ·  {kb:,.0f} KB/s")

    def update_status(self, task: DownloadTask) -> None:
        self.task = task
        self._status.setText(task.status.value)
        self._bar.setValue(int(task.progress * 1000))
        if task.status == DownloadStatus.FAILED and task.error:
            self._meta.setText(f"{task.file_path}\n{task.error}")
