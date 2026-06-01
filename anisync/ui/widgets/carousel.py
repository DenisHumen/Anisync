"""Horizontal poster carousel with smooth animated paging.

Apple-TV / Crunchyroll style:

* Section kicker + big title (with optional "See all" link).
* Horizontal strip of :class:`PosterCard`s with smooth scrolling.
* Chevron buttons appear at the edges on hover and page the strip by
  one viewport width using a property animation.
"""
from __future__ import annotations

from typing import Callable, Iterable

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from anisync.core.models import AnimeSummary
from anisync.ui.widgets.anime_card import POSTER_H, POSTER_W, PosterCard


class Carousel(QFrame):
    open_details = Signal(object)
    see_all = Signal()

    def __init__(
        self,
        title: str,
        *,
        kicker: str | None = None,
        show_see_all: bool = False,
        poster_size: tuple[int, int] = (POSTER_W, POSTER_H),
    ) -> None:
        super().__init__()
        self._poster_size = poster_size
        self.setObjectName("carousel")
        self.setStyleSheet("background: transparent;")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        # ── header (kicker + title + see all) ──
        head = QHBoxLayout()
        head.setContentsMargins(64, 0, 64, 0)
        head.setSpacing(12)

        col = QVBoxLayout()
        col.setSpacing(2)
        if kicker:
            k = QLabel(kicker)
            k.setObjectName("kicker")
            col.addWidget(k)
        t = QLabel(title)
        t.setObjectName("h2")
        col.addWidget(t)
        head.addLayout(col)
        head.addStretch(1)

        if show_see_all:
            btn = QPushButton("See all  ›")
            btn.setProperty("ghost", True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(self.see_all.emit)
            head.addWidget(btn)
        outer.addLayout(head)

        # ── scroll strip ──
        strip_wrap = QFrame()
        strip_wrap.setStyleSheet("background: transparent;")
        wrap_layout = QHBoxLayout(strip_wrap)
        wrap_layout.setContentsMargins(0, 0, 0, 0)
        wrap_layout.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("background: transparent;")
        # generous fixed height for full poster + label + scale padding
        self._scroll.setFixedHeight(poster_size[1] + 44 + 24 + 12)

        self._row_widget = QWidget()
        self._row = QHBoxLayout(self._row_widget)
        # Wider gutter so floating chevrons don't overlap the first/last card.
        self._row.setContentsMargins(72, 0, 72, 0)
        self._row.setSpacing(8)
        self._row.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._scroll.setWidget(self._row_widget)
        wrap_layout.addWidget(self._scroll)

        outer.addWidget(strip_wrap)

        # ── chevron buttons (floating, absolute positioned) ──
        self._left = QPushButton("‹", strip_wrap)
        self._right = QPushButton("›", strip_wrap)
        for b in (self._left, self._right):
            b.setProperty("chev", True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFixedSize(40, 40)
            b.setStyleSheet(
                "QPushButton {"
                "  background: rgba(20,20,28,210);"
                "  color:#fff; border:1px solid rgba(255,255,255,30);"
                "  border-radius:20px; font-size:20px; font-weight:600;"
                "}"
                "QPushButton:hover { background: rgba(40,40,52,235); }"
            )
            b.hide()
        self._left.clicked.connect(lambda: self._page(-1))
        self._right.clicked.connect(lambda: self._page(1))
        strip_wrap.installEventFilter(self)
        self._strip_wrap = strip_wrap

        self._scroll_anim: QPropertyAnimation | None = None

    # ── public API ────────────────────────────────────────────────────────

    def populate(
        self,
        items: Iterable[AnimeSummary],
        *,
        on_click: Callable[[AnimeSummary], None] | None = None,
    ) -> None:
        self._clear()
        click = on_click or self.open_details.emit
        for s in items:
            card = PosterCard(s, on_click=click, size=self._poster_size)
            self._row.addWidget(card)
        # trailing flex
        self._row.addStretch(1)

    def is_empty(self) -> bool:
        # last item is the stretch
        return self._row.count() <= 1

    # ── internals ─────────────────────────────────────────────────────────

    def _clear(self) -> None:
        while self._row.count():
            item = self._row.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _page(self, direction: int) -> None:
        bar = self._scroll.horizontalScrollBar()
        if not bar:
            return
        step = max(self._scroll.viewport().width() - 80, 200)
        target = max(0, min(bar.maximum(), bar.value() + direction * step))
        # Same lifetime trap as PosterCard: never use DeleteWhenStopped
        # while keeping a Python reference to the animation.
        prev = self._scroll_anim
        self._scroll_anim = None
        if prev is not None:
            try:
                prev.stop()
                prev.deleteLater()
            except RuntimeError:
                pass
        anim = QPropertyAnimation(bar, b"value", self)
        anim.setDuration(380)
        anim.setStartValue(bar.value())
        anim.setEndValue(target)
        anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        anim.finished.connect(lambda: setattr(self, "_scroll_anim", None))
        self._scroll_anim = anim
        anim.start()

    def resizeEvent(self, evt):  # noqa: N802
        super().resizeEvent(evt)
        self._position_chevrons()

    def eventFilter(self, obj, evt):  # noqa: N802
        from PySide6.QtCore import QEvent

        if obj is self._strip_wrap:
            if evt.type() == QEvent.Type.Enter:
                self._left.show()
                self._right.show()
                self._position_chevrons()
            elif evt.type() == QEvent.Type.Leave:
                self._left.hide()
                self._right.hide()
            elif evt.type() == QEvent.Type.Resize:
                self._position_chevrons()
        return super().eventFilter(obj, evt)

    def _position_chevrons(self) -> None:
        h = self._strip_wrap.height()
        # Anchor chevrons over the poster image (not under the title)
        # to avoid covering the title and to keep them centered visually.
        y = max(8, (h - self._right.height()) // 2 - 18)
        # Place them in the outer gutter so they sit BESIDE the cards,
        # not on top of them.
        self._left.move(16, y)
        self._right.move(self._strip_wrap.width() - self._right.width() - 16, y)
        self._left.raise_()
        self._right.raise_()
