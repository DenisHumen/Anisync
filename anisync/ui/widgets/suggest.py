"""Suggestion dropdown shown under a search QLineEdit."""
from __future__ import annotations


from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from anisync.core.models import AnimeSummary


class SuggestPopup(QFrame):
    pick = Signal(object)        # AnimeSummary
    submit_query = Signal(str)   # "See all results for X"

    def __init__(self, anchor: QWidget) -> None:
        super().__init__(anchor.window())
        self.setObjectName("suggest")
        self.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self._anchor = anchor
        self._vbox = QVBoxLayout(self)
        self._vbox.setContentsMargins(8, 8, 8, 8)
        self._vbox.setSpacing(2)
        self.hide()

    def set_results(self, query: str, results: list[AnimeSummary]) -> None:
        self._clear()
        if not results:
            empty = QLabel("No matches yet…")
            empty.setObjectName("dim")
            empty.setContentsMargins(12, 8, 12, 8)
            self._vbox.addWidget(empty)
            self._show_at_anchor()
            return
        for r in results[:8]:
            self._vbox.addWidget(self._row(r))
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: rgba(255,255,255,40);")
        self._vbox.addWidget(sep)
        seeall = QPushButton(f"See all results for “{query}”  →")
        seeall.setCursor(Qt.CursorShape.PointingHandCursor)
        seeall.clicked.connect(lambda: self.submit_query.emit(query))
        self._vbox.addWidget(seeall)
        self._show_at_anchor()

    def _row(self, r: AnimeSummary) -> QWidget:
        btn = QPushButton()
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        h = QHBoxLayout(btn)
        h.setContentsMargins(8, 4, 8, 4)
        h.setSpacing(10)
        title = QLabel(r.title)
        title.setStyleSheet("font-weight:600;")
        h.addWidget(title, 1)
        meta_parts: list[str] = []
        if r.year:
            meta_parts.append(str(r.year))
        if r.type:
            meta_parts.append(r.type)
        if r.episodes_count:
            meta_parts.append(f"{r.episodes_count} ep")
        if meta_parts:
            m = QLabel(" · ".join(meta_parts))
            m.setObjectName("dim")
            h.addWidget(m)
        btn.clicked.connect(lambda: self.pick.emit(r))
        return btn

    def _show_at_anchor(self) -> None:
        win = self._anchor.window()
        top_left = self._anchor.mapTo(win, QPoint(0, self._anchor.height() + 6))
        global_pos = win.mapToGlobal(top_left)
        self.setFixedWidth(self._anchor.width())
        self.move(global_pos)
        self.adjustSize()
        self.show()
        self.raise_()

    def _clear(self) -> None:
        while self._vbox.count():
            item = self._vbox.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
