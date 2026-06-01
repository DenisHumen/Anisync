"""Bottom toast for non-blocking messages."""
from __future__ import annotations

import re

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


class Snackbar(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("snackbar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        self._label = QLabel("")
        layout.addWidget(self._label)
        self.hide()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show_message(self, text: str, *, level: str = "info", ms: int = 4000) -> None:
        self.setProperty("level", level)
        clean = _ANSI_RE.sub("", text).strip()
        if len(clean) > 240:
            clean = clean[:237] + "\u2026"
        self._label.setText(clean)
        self.style().unpolish(self)
        self.style().polish(self)
        self.show()
        self.raise_()
        self._timer.start(ms)
