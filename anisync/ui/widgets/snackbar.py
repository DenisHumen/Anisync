"""Bottom toast for non-blocking messages."""
from __future__ import annotations

import re

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QTimer, Qt
from PySide6.QtWidgets import QGraphicsOpacityEffect, QHBoxLayout, QLabel, QWidget

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
        self._fade_anim: QPropertyAnimation | None = None

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
        self._fade_in()
        self._timer.start(ms)

    def _fade_in(self) -> None:
        prev = self._fade_anim
        self._fade_anim = None
        if prev is not None:
            try:
                prev.stop()
            except RuntimeError:
                pass
        eff = QGraphicsOpacityEffect(self)
        eff.setOpacity(0.0)
        self.setGraphicsEffect(eff)  # deletes any previous effect
        anim = QPropertyAnimation(eff, b"opacity", self)
        anim.setDuration(180)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        def _done() -> None:
            self._fade_anim = None
            self.setGraphicsEffect(None)

        anim.finished.connect(_done)
        self._fade_anim = anim
        anim.start()
