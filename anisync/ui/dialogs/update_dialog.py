"""Dialog showing a newer GitHub release."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
)

import anisync
from anisync.core.updater import ReleaseAsset, ReleaseInfo, UpdateService
from anisync.utils.async_runner import run_async
from anisync.utils.paths import data_dir


class UpdateDialog(QDialog):
    def __init__(self, release: ReleaseInfo, parent=None) -> None:
        super().__init__(parent)
        self._release = release
        self.setWindowTitle("Update available")
        self.setModal(True)
        self.resize(540, 460)

        v = QVBoxLayout(self)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(12)

        head = QLabel(f"Anisync <b>{release.version}</b> is available")
        head.setObjectName("h2")
        v.addWidget(head)

        sub = QLabel(f"You are running v{anisync.__version__}.")
        sub.setObjectName("muted")
        v.addWidget(sub)

        body = QTextBrowser()
        body.setMarkdown(release.body or "_No release notes._")
        body.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        v.addWidget(body, 1)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.hide()
        v.addWidget(self._progress)

        self._status = QLabel("")
        self._status.setObjectName("muted")
        v.addWidget(self._status)

        btns = QHBoxLayout()
        btns.addStretch(1)
        later = QPushButton("Later")
        later.setProperty("ghost", True)
        later.clicked.connect(self.reject)
        btns.addWidget(later)

        notes = QPushButton("View on GitHub")
        notes.setProperty("ghost", True)
        notes.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(release.html_url)))
        btns.addWidget(notes)

        self._dl_btn = QPushButton("Download installer")
        self._dl_btn.setProperty("accent", True)
        self._dl_btn.clicked.connect(self._do_download)
        btns.addWidget(self._dl_btn)
        v.addLayout(btns)

    def _do_download(self) -> None:
        asset = self._release.asset_for_platform()
        if asset is None:
            self._status.setText("No installer attached for your platform.")
            return
        self._dl_btn.setEnabled(False)
        self._progress.show()
        self._progress.setValue(0)
        self._status.setText(f"Downloading {asset.name}…")
        dest = data_dir() / "updates"
        run_async(
            UpdateService().download_asset(asset, dest),
            on_done=self._on_downloaded,
            on_error=self._on_err,
        )

    def _on_downloaded(self, path: Path) -> None:
        self._progress.setValue(100)
        self._status.setText(f"Saved to: {path}")
        self._dl_btn.setText("Open installer")
        self._dl_btn.setEnabled(True)
        try:
            self._dl_btn.clicked.disconnect()
        except RuntimeError:
            pass
        self._dl_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))))

    def _on_err(self, exc: Exception) -> None:
        self._dl_btn.setEnabled(True)
        self._progress.hide()
        self._status.setText(f"Download failed: {exc}")
