"""Apple-TV-style top navigation bar.

A thin translucent strip pinned at the top: wordmark on the left,
nav buttons in the middle, search shortcut + account on the right. On
non-macOS platforms we also embed traffic-light-style window controls.
"""
from __future__ import annotations

import sys

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QWidget,
)


def _make_search_icon(color: str = "#FFFFFF", px: int = 18) -> QIcon:
    """Draw a crisp magnifier glyph so we never depend on a font that
    happens to ship the ``⌕`` codepoint (most don't → tofu box)."""
    scale = 4  # render high-res then let Qt downscale for retina crispness
    size = px * scale
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(QColor(color))
    pen.setWidth(2 * scale)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    # lens (circle) in the upper-left, handle toward the lower-right
    d = int(size * 0.55)
    m = int(size * 0.10)
    p.drawEllipse(m, m, d, d)
    p.drawLine(m + d - int(d * 0.15), m + d - int(d * 0.15),
               size - m, size - m)
    p.end()
    return QIcon(pm)


class TopNav(QFrame):
    nav_clicked = Signal(str)        # internal page key
    search_clicked = Signal()

    def __init__(self, items: list[tuple[str, str]], parent: QWidget | None = None) -> None:
        """``items`` = ``[(key, label), …]`` displayed left-to-right."""
        super().__init__(parent)
        self.setObjectName("topnav")
        self.setFixedHeight(56)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._drag_pos: QPoint | None = None
        self._is_mac = sys.platform == "darwin"

        h = QHBoxLayout(self)
        h.setContentsMargins(24, 0, 24, 0)
        h.setSpacing(20)

        if self._is_mac:
            # native-looking traffic lights, drawn by us since the window
            # is frameless. Sit on the very left.
            h.addLayout(self._build_traffic_lights())
            h.addSpacing(12)

        # Wordmark (logo mark + text)
        from anisync.ui.assets import logo_path
        lp = logo_path()
        if lp.exists():
            mark = QLabel()
            pm = QPixmap(str(lp)).scaled(
                26, 26,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            mark.setPixmap(pm)
            h.addWidget(mark)
            h.addSpacing(8)
        word = QLabel("ANISYNC")
        word.setObjectName("wordmark")
        h.addWidget(word)
        h.addSpacing(28)

        # Nav buttons
        self._buttons: dict[str, QPushButton] = {}
        for key, label in items:
            btn = QPushButton(label)
            btn.setProperty("class", "nav")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, k=key: self.nav_clicked.emit(k))
            h.addWidget(btn)
            self._buttons[key] = btn

        h.addStretch(1)

        # Right side: search + account
        search = QPushButton()
        search.setIcon(_make_search_icon())
        search.setIconSize(QSize(18, 18))
        search.setProperty("icon", True)
        search.setToolTip("Search")
        search.setCursor(Qt.CursorShape.PointingHandCursor)
        search.clicked.connect(self.search_clicked.emit)
        h.addWidget(search)

        if not self._is_mac:
            h.addSpacing(12)
            h.addLayout(self._build_window_controls())

    # ── helpers ───────────────────────────────────────────────────────────

    def set_active(self, key: str) -> None:
        for k, b in self._buttons.items():
            b.setProperty("active", k == key)
            b.style().unpolish(b); b.style().polish(b)

    def _build_traffic_lights(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)
        for role, action in (
            ("close", lambda: self.window().close()),
            ("min",   lambda: self.window().showMinimized()),
            ("max",   self._toggle_max),
        ):
            b = QPushButton()
            b.setObjectName("winBtn")
            b.setProperty("role", role)
            b.setFixedSize(12, 12)        # the QSS would be ignored if size policy expands
            b.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(action)
            layout.addWidget(b)
        return layout

    def _build_window_controls(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(0, 0, 0, 0)
        for label, action in (
            ("—", lambda: self.window().showMinimized()),
            ("▢", self._toggle_max),
            ("✕", lambda: self.window().close()),
        ):
            b = QPushButton(label)
            b.setProperty("ghost", True)
            b.setFixedSize(34, 28)
            b.clicked.connect(action)
            layout.addWidget(b)
        return layout

    def _toggle_max(self) -> None:
        win = self.window()
        if win.isMaximized():
            win.showNormal()
        else:
            win.showMaximized()

    # ── window drag (frameless) ──────────────────────────────────────────

    def mousePressEvent(self, e: QMouseEvent):  # noqa: N802
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.window().frameGeometry().topLeft()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e: QMouseEvent):  # noqa: N802
        if self._drag_pos is not None and e.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(e.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e: QMouseEvent):  # noqa: N802
        self._drag_pos = None
        super().mouseReleaseEvent(e)

    def mouseDoubleClickEvent(self, e: QMouseEvent):  # noqa: N802
        if e.button() == Qt.MouseButton.LeftButton:
            self._toggle_max()
        super().mouseDoubleClickEvent(e)
