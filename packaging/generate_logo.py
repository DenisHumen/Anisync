"""Generate the Anisync app logo + platform icon files.

Vector-drawn with QPainter (crisp at any size), then exported to:

* ``anisync.png``   — 1024² master (Linux / general use)
* ``anisync.icns``  — macOS app icon (via ``iconutil``)
* ``anisync.ico``   — Windows app icon (via Pillow)
* ``anisync_mark.png`` — 256² mark for in-app use

Design: a brand orange→red squircle with a white rounded play triangle
and a broken "sync" orbit ring. Run from the repo root:

    .venv/bin/python packaging/generate_logo.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import (  # noqa: E402
    QBrush,
    QColor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import QApplication  # noqa: E402

HERE = Path(__file__).resolve().parent

ACCENT = "#F47521"      # Crunchyroll orange
ACCENT_MID = "#FF5E3A"
ACCENT_END = "#FF4D6D"  # orange → red


def render(size: int, *, bg: bool = True) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHints(
        QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform
    )
    s = float(size)

    if bg:
        # ── squircle background with brand gradient ──
        radius = s * 0.2235
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, s, s), radius, radius)
        grad = QLinearGradient(0, 0, s, s)
        grad.setColorAt(0.0, QColor(ACCENT))
        grad.setColorAt(0.55, QColor(ACCENT_MID))
        grad.setColorAt(1.0, QColor(ACCENT_END))
        p.fillPath(path, QBrush(grad))

        # soft top highlight for depth
        glow = QRadialGradient(s * 0.5, s * 0.12, s * 0.7)
        hi = QColor(255, 255, 255, 60)
        glow.setColorAt(0.0, hi)
        glow.setColorAt(0.5, QColor(255, 255, 255, 0))
        p.fillPath(path, QBrush(glow))
        p.setClipPath(path)

    cx, cy = s * 0.5, s * 0.5

    # ── "sync" orbit: a broken ring around the play button ──
    ring_pen = QPen(QColor(255, 255, 255, 150))
    ring_pen.setWidthF(s * 0.035)
    ring_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(ring_pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    r = s * 0.34
    orbit = QRectF(cx - r, cy - r, 2 * r, 2 * r)
    # two opposing arcs leave a gap → reads as a refresh/sync loop
    p.drawArc(orbit, int(35 * 16), int(120 * 16))
    p.drawArc(orbit, int(215 * 16), int(120 * 16))

    # ── white rounded play triangle ──
    tri = s * 0.20
    pts = [
        QPointF(cx - tri * 0.72, cy - tri),
        QPointF(cx + tri, cy),
        QPointF(cx - tri * 0.72, cy + tri),
    ]
    play = QPainterPath()
    play.moveTo(pts[0])
    play.lineTo(pts[1])
    play.lineTo(pts[2])
    play.closeSubpath()
    pen = QPen(QColor("#FFFFFF"))
    pen.setWidthF(s * 0.055)            # round pen → rounded triangle corners
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(QBrush(QColor("#FFFFFF")))
    p.drawPath(play)

    p.end()
    return pm


def save_png(pm: QPixmap, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pm.save(str(path), "PNG")
    print("wrote", path.relative_to(HERE.parent), pm.size().width())


def main() -> int:
    QApplication(sys.argv)

    master = render(1024)
    save_png(master, HERE / "anisync.png")
    save_png(render(256), HERE / "anisync_mark.png")
    # Runtime copy bundled inside the package (window/taskbar icon).
    save_png(render(256), HERE.parent / "anisync" / "ui" / "assets" / "logo.png")

    # ── macOS .icns via iconutil ──
    iconset = HERE / "anisync.iconset"
    iconset.mkdir(exist_ok=True)
    icns_sizes = [16, 32, 64, 128, 256, 512, 1024]
    base = {16: "16x16", 32: "32x32", 64: "64x64", 128: "128x128",
            256: "256x256", 512: "512x512", 1024: "512x512@2x"}
    for px in icns_sizes:
        pm = render(px)
        name = base[px]
        pm.save(str(iconset / f"icon_{name}.png"), "PNG")
        # @2x variants
        if px in (16, 32, 128, 256, 512):
            big = render(px * 2)
            big.save(str(iconset / f"icon_{base[px]}@2x.png"), "PNG")
    if sys.platform == "darwin":
        subprocess.run(
            ["iconutil", "-c", "icns", str(iconset), "-o", str(HERE / "anisync.icns")],
            check=True,
        )
        print("wrote packaging/anisync.icns")
    else:
        print("skip .icns (iconutil is macOS-only)")

    # ── Windows .ico via Pillow ──
    try:
        from PIL import Image
        png1024 = HERE / "anisync.png"
        img = Image.open(png1024).convert("RGBA")
        img.save(
            HERE / "anisync.ico",
            sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
        )
        print("wrote packaging/anisync.ico")
    except Exception as e:  # noqa: BLE001
        print("skip .ico:", e)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
