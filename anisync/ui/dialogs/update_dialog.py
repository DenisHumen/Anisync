"""Dialog offering to install a newer GitHub release.

Opens on startup when a newer version exists (and from Settings →
"Check for updates"). Shows the combined release notes of **every**
version the user has missed — pulled straight from the GitHub release
bodies — then, on "Install update", downloads the platform asset with
live progress and:

* packaged builds → stages the new build and swap-relaunches
  (:mod:`anisync.core.selfupdate`);
* dev / non-writable installs → saves the installer and offers to
  open it manually.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl, Signal
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
from anisync.core import selfupdate
from anisync.core.updater import (
    ReleaseInfo,
    UpdateService,
    compose_release_notes_md,
)
from anisync.utils.async_runner import run_async
from anisync.utils.paths import data_dir


def _fmt_mb(n: int) -> str:
    return f"{n / (1024 * 1024):.1f} MB"


class UpdateDialog(QDialog):
    # Download progress arrives from the async worker thread; emitting a
    # signal is thread-safe (Qt queues it onto the GUI thread).
    _sig_progress = Signal(int, int)

    def __init__(
        self,
        release: ReleaseInfo,
        news: list[ReleaseInfo] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._release = release
        self._news = news or [release]
        self.setWindowTitle("Update available")
        self.setModal(True)
        self.resize(600, 540)

        v = QVBoxLayout(self)
        v.setContentsMargins(28, 24, 28, 20)
        v.setSpacing(10)

        kicker = QLabel("UPDATE AVAILABLE")
        kicker.setObjectName("kicker")
        v.addWidget(kicker)

        head = QLabel(f"Anisync {release.version}")
        head.setObjectName("h1")
        v.addWidget(head)

        sub_bits = []
        if release.published_at:
            sub_bits.append(f"Released {release.published_at.strftime('%d %b %Y')}")
        sub_bits.append(f"You're on v{anisync.__version__}")
        missed = len(self._news)
        if missed > 1:
            sub_bits.append(f"{missed} versions since your build")
        sub = QLabel("  ·  ".join(sub_bits))
        sub.setObjectName("muted")
        v.addWidget(sub)

        v.addSpacing(6)

        notes = QTextBrowser()
        notes.setObjectName("releaseNotes")
        notes.setOpenExternalLinks(True)
        notes.setMarkdown(
            compose_release_notes_md(self._news, current_version=anisync.__version__)
        )
        notes.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        v.addWidget(notes, 1)

        self._progress = QProgressBar()
        self._progress.setRange(0, 1000)
        self._progress.hide()
        v.addWidget(self._progress)

        self._status = QLabel("")
        self._status.setObjectName("muted")
        self._status.setWordWrap(True)
        v.addWidget(self._status)

        btns = QHBoxLayout()
        btns.setSpacing(10)
        gh = QPushButton("View on GitHub")
        gh.setProperty("ghost", True)
        gh.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(release.html_url)))
        btns.addWidget(gh)
        btns.addStretch(1)

        self._later_btn = QPushButton("Later")
        self._later_btn.setObjectName("outlined")
        self._later_btn.clicked.connect(self.reject)
        btns.addWidget(self._later_btn)

        self._can_self_update = selfupdate.can_self_update()
        self._install_btn = QPushButton(
            "Install update" if self._can_self_update else "Download installer"
        )
        self._install_btn.setProperty("accent", True)
        self._install_btn.clicked.connect(self._do_install)
        btns.addWidget(self._install_btn)
        v.addLayout(btns)

        self._sig_progress.connect(self._on_progress)

    # ── download ──────────────────────────────────────────────────────────

    def _do_install(self) -> None:
        asset = self._release.asset_for_platform()
        if asset is None:
            self._status.setText(
                "No installer is attached for your platform — "
                "use “View on GitHub” to download manually."
            )
            return
        self._install_btn.setEnabled(False)
        self._progress.show()
        self._progress.setValue(0)
        self._status.setText(f"Downloading {asset.name}…")
        run_async(
            UpdateService().download_asset(
                asset, data_dir() / "updates", progress=self._sig_progress.emit
            ),
            on_done=self._on_downloaded,
            on_error=self._on_err,
        )

    def _on_progress(self, done: int, total: int) -> None:
        if total > 0:
            self._progress.setRange(0, 1000)
            self._progress.setValue(min(1000, int(done / total * 1000)))
            self._status.setText(f"Downloading…  {_fmt_mb(done)} / {_fmt_mb(total)}")
        else:
            self._progress.setRange(0, 0)  # indeterminate
            self._status.setText(f"Downloading…  {_fmt_mb(done)}")

    def _on_downloaded(self, path: Path) -> None:
        self._progress.setRange(0, 1000)
        self._progress.setValue(1000)
        if self._can_self_update:
            self._status.setText("Installing update…")
            self._later_btn.setEnabled(False)
            # Unpack off the UI thread, then swap + relaunch.
            run_async(
                _stage_async(path),
                on_done=self._on_staged,
                on_error=self._on_err,
            )
            return
        # Fallback (dev runs / non-writable installs): reveal the download.
        self._status.setText(f"Saved to: {path}")
        self._install_btn.setText("Open installer")
        self._install_btn.setEnabled(True)
        try:
            self._install_btn.clicked.disconnect()
        except RuntimeError:
            pass
        self._install_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        )

    def _on_staged(self, new_artifact: Path) -> None:
        from PySide6.QtWidgets import QApplication

        self._status.setText("Restarting to finish the update…")
        selfupdate.apply_and_relaunch(new_artifact)
        QApplication.quit()

    def _on_err(self, exc: Exception) -> None:
        self._install_btn.setEnabled(True)
        self._later_btn.setEnabled(True)
        self._progress.hide()
        self._status.setText(f"Update failed: {exc}")


async def _stage_async(asset_path: Path) -> Path:
    import asyncio

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, selfupdate.stage, asset_path)
