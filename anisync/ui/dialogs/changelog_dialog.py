"""Release-history dialog — every published version, its date and notes.

Fetched live from the GitHub Releases API (release bodies are the
changelog). The running version is badged *installed*, anything newer
is badged *new*. Falls back to a friendly offline message when GitHub
is unreachable.
"""
from __future__ import annotations

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
)

import anisync
from anisync.core.updater import (
    ReleaseInfo,
    UpdateService,
    compose_release_notes_md,
)
from anisync.ui.widgets.spinner import LoadingPanel
from anisync.utils.async_runner import run_async


class ChangelogDialog(QDialog):
    def __init__(
        self,
        repo: str,
        parent=None,
        *,
        releases: list[ReleaseInfo] | None = None,
    ) -> None:
        """``releases`` lets callers/tests inject preloaded data; when
        omitted the dialog fetches the history itself."""
        super().__init__(parent)
        self._repo = repo
        self.setWindowTitle("What's new")
        self.setModal(True)
        self.resize(640, 580)

        v = QVBoxLayout(self)
        v.setContentsMargins(28, 24, 28, 20)
        v.setSpacing(10)
        self._v = v

        kicker = QLabel("RELEASE HISTORY")
        kicker.setObjectName("kicker")
        v.addWidget(kicker)

        title = QLabel("What's new")
        title.setObjectName("h1")
        v.addWidget(title)

        sub = QLabel(f"Updates published on GitHub  ·  you're on v{anisync.__version__}")
        sub.setObjectName("muted")
        v.addWidget(sub)

        v.addSpacing(6)

        # Placeholder swapped for the notes browser once data arrives.
        self._content: QLabel | QTextBrowser | LoadingPanel = LoadingPanel(
            "Fetching release history…"
        )
        v.addWidget(self._content, 1)

        btns = QHBoxLayout()
        btns.setSpacing(10)
        gh = QPushButton("View on GitHub")
        gh.setProperty("ghost", True)
        gh.clicked.connect(
            lambda: QDesktopServices.openUrl(
                QUrl(f"https://github.com/{self._repo}/releases")
            )
        )
        btns.addWidget(gh)
        btns.addStretch(1)
        close = QPushButton("Close")
        close.setObjectName("outlined")
        close.clicked.connect(self.accept)
        btns.addWidget(close)
        v.addLayout(btns)

        if releases is not None:
            self._show(releases)
        else:
            run_async(
                UpdateService(repo).releases(limit=15),
                on_done=self._show,
                on_error=lambda _e: self._fail(),
            )

    # ── states ────────────────────────────────────────────────────────────

    def _swap(self, widget) -> None:
        self._v.replaceWidget(self._content, widget)
        self._content.deleteLater()
        self._content = widget

    def _show(self, releases: list[ReleaseInfo]) -> None:
        if not releases:
            self._fail("No releases have been published yet.")
            return
        browser = QTextBrowser()
        browser.setObjectName("releaseNotes")
        browser.setOpenExternalLinks(True)
        browser.setMarkdown(
            compose_release_notes_md(releases, current_version=anisync.__version__)
        )
        browser.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._swap(browser)

    def _fail(self, message: str | None = None) -> None:
        lbl = QLabel(
            message
            or "Couldn't load the release history.\n"
               "Check your connection or open the releases page on GitHub."
        )
        lbl.setObjectName("muted")
        lbl.setWordWrap(True)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._swap(lbl)
