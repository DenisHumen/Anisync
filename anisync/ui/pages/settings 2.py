"""Settings page."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from anisync.core.config import Config


class SettingsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._cfg = Config.load()

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 24, 32, 24)
        root.setSpacing(16)

        title = QLabel("Settings")
        title.setObjectName("h1")
        root.addWidget(title)

        form = QFormLayout()
        form.setSpacing(12)

        self._dir = QLineEdit(self._cfg.downloads_dir)
        dir_row = QHBoxLayout()
        dir_row.addWidget(self._dir, 1)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        dir_row.addWidget(browse)
        form.addRow("Downloads folder", dir_row)

        self._concurrent = QSpinBox()
        self._concurrent.setRange(1, 10)
        self._concurrent.setValue(self._cfg.max_concurrent_downloads)
        form.addRow("Max concurrent downloads", self._concurrent)

        self._quality = QComboBox()
        self._quality.addItems(["360p", "480p", "720p", "1080p", "1440p", "2160p"])
        if self._cfg.preferred_quality in [self._quality.itemText(i) for i in range(self._quality.count())]:
            self._quality.setCurrentText(self._cfg.preferred_quality)
        form.addRow("Preferred quality", self._quality)

        self._dub = QLineEdit(self._cfg.preferred_dub)
        form.addRow("Preferred dub (leave empty for auto)", self._dub)

        root.addLayout(form)

        save = QPushButton("Save")
        save.setProperty("accent", True)
        save.clicked.connect(self._save)
        root.addWidget(save)
        root.addStretch(1)

    def _browse(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Downloads folder", self._dir.text())
        if d:
            self._dir.setText(d)

    def _save(self) -> None:
        self._cfg.downloads_dir = self._dir.text()
        self._cfg.max_concurrent_downloads = self._concurrent.value()
        self._cfg.preferred_quality = self._quality.currentText()
        self._cfg.preferred_dub = self._dub.text()
        self._cfg.save()
