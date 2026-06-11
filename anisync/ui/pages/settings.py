"""Settings page — centered card layout."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from anisync.core.config import Config


class SettingsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._cfg = Config.load()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        outer.addWidget(scroll)

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        scroll.setWidget(body)

        body_l = QVBoxLayout(body)
        body_l.setContentsMargins(64, 32, 64, 60)
        body_l.setSpacing(24)

        # Header (left-aligned, full-width)
        kicker = QLabel("PREFERENCES")
        kicker.setObjectName("kicker")
        body_l.addWidget(kicker)

        title = QLabel("Settings")
        title.setObjectName("h1")
        body_l.addWidget(title)

        # Centered card
        card_row = QHBoxLayout()
        card_row.addStretch(1)
        card = QFrame()
        card.setObjectName("card")
        card.setMinimumWidth(560)
        card.setMaximumWidth(720)
        card_row.addWidget(card)
        card_row.addStretch(1)
        body_l.addLayout(card_row)

        c = QVBoxLayout(card)
        c.setContentsMargins(28, 28, 28, 28)
        c.setSpacing(18)

        # Section: downloads
        c.addWidget(self._section_label("Downloads"))
        form = QFormLayout()
        form.setSpacing(14)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self._dir = QLineEdit(self._cfg.downloads_dir)
        dir_row = QHBoxLayout()
        dir_row.addWidget(self._dir, 1)
        browse = QPushButton("Browse…")
        browse.setObjectName("outlined")
        browse.clicked.connect(self._browse)
        dir_row.addWidget(browse)
        form.addRow("Folder", dir_row)

        self._concurrent = QSpinBox()
        self._concurrent.setRange(1, 10)
        self._concurrent.setValue(self._cfg.max_concurrent_downloads)
        form.addRow("Max concurrent", self._concurrent)

        self._quality = QComboBox()
        # (label, stored-value) — "best" auto-picks the highest available.
        self._quality_choices = [
            ("Best available", "best"),
            ("2160p", "2160p"),
            ("1440p", "1440p"),
            ("1080p", "1080p"),
            ("720p", "720p"),
            ("480p", "480p"),
            ("360p", "360p"),
        ]
        for label, value in self._quality_choices:
            self._quality.addItem(label, value)
        current = self._cfg.preferred_quality or "best"
        for i, (_label, value) in enumerate(self._quality_choices):
            if value == current:
                self._quality.setCurrentIndex(i)
                break
        form.addRow("Preferred quality", self._quality)

        self._dub = QLineEdit(self._cfg.preferred_dub)
        self._dub.setPlaceholderText("auto")
        form.addRow("Preferred dub", self._dub)

        c.addLayout(form)

        # Section: playback
        c.addSpacing(6)
        c.addWidget(self._section_label("Playback"))
        self._autoplay = QCheckBox("Autoplay next episode when one finishes")
        self._autoplay.setChecked(self._cfg.autoplay_next)
        c.addWidget(self._autoplay)

        # Section: updates
        c.addSpacing(6)
        c.addWidget(self._section_label("Updates"))
        self._check_updates = QCheckBox("Check for updates on startup")
        self._check_updates.setChecked(self._cfg.check_updates_on_start)
        c.addWidget(self._check_updates)

        # Footer actions
        c.addSpacing(8)
        actions = QHBoxLayout()
        actions.addStretch(1)
        self._save_btn = QPushButton("Save changes")
        self._save_btn.setObjectName("primary")
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_btn.clicked.connect(self._save)
        actions.addWidget(self._save_btn)
        c.addLayout(actions)

        body_l.addStretch(1)

    @staticmethod
    def _section_label(text: str) -> QLabel:
        lbl = QLabel(text.upper())
        lbl.setStyleSheet(
            "color:#8A8A95; font-size:11px; font-weight:700; letter-spacing:2px;"
        )
        return lbl

    def _browse(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Downloads folder", self._dir.text())
        if d:
            self._dir.setText(d)

    def _save(self) -> None:
        self._cfg.downloads_dir = self._dir.text()
        self._cfg.max_concurrent_downloads = self._concurrent.value()
        self._cfg.preferred_quality = self._quality.currentData() or "best"
        self._cfg.preferred_dub = self._dub.text()
        self._cfg.autoplay_next = self._autoplay.isChecked()
        self._cfg.check_updates_on_start = self._check_updates.isChecked()
        self._cfg.save()
        # Apply the new preferences to the running download manager so a
        # restart isn't needed for them to take effect.
        from anisync.core.downloader import get_manager
        get_manager().reload_config()
        self._confirm_saved()

    def _confirm_saved(self) -> None:
        from PySide6.QtCore import QTimer
        self._save_btn.setText("Saved ✓")
        self._save_btn.setEnabled(False)
        QTimer.singleShot(1400, self._reset_save_btn)

    def _reset_save_btn(self) -> None:
        self._save_btn.setText("Save changes")
        self._save_btn.setEnabled(True)
