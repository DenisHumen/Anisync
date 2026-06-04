"""Color palette + global QSS (Crunchyroll-inspired)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    bg: str = "#0B0B0F"
    bg_alt: str = "#111118"
    surface: str = "#15151B"
    surface_hover: str = "#1E1E27"
    border: str = "#23232E"
    text: str = "#FFFFFF"
    text_muted: str = "#A8A8B3"
    text_dim: str = "#6E6E7A"
    accent: str = "#F47521"          # Crunchyroll orange
    accent_hover: str = "#FF8A3D"
    accent_pressed: str = "#D2611A"
    success: str = "#43B581"
    danger: str = "#ED4245"


PALETTE = Palette()


def build_qss(p: Palette = PALETTE) -> str:
    return f"""
    * {{
        font-family: "SF Pro Display", "Segoe UI", "Helvetica Neue", Arial, sans-serif;
        color: {p.text};
    }}
    QWidget {{ background: {p.bg}; }}

    QToolTip {{
        background: {p.surface};
        color: {p.text};
        border: 1px solid {p.border};
        padding: 4px 8px;
        border-radius: 4px;
    }}

    /* ── Sidebar ─────────────────────────────────────────────── */
    #sidebar {{
        background: {p.bg_alt};
        border-right: 1px solid {p.border};
    }}
    #sidebar QPushButton {{
        background: transparent;
        text-align: left;
        padding: 10px 16px;
        border: none;
        border-radius: 8px;
        color: {p.text_muted};
        font-size: 14px;
        font-weight: 500;
    }}
    #sidebar QPushButton:hover {{
        background: {p.surface};
        color: {p.text};
    }}
    #sidebar QPushButton[active="true"] {{
        background: {p.accent};
        color: white;
    }}
    #sidebar #logo {{
        color: {p.accent};
        font-size: 22px;
        font-weight: 800;
        padding: 16px;
        letter-spacing: 1px;
    }}

    /* ── Top bar ─────────────────────────────────────────────── */
    #topbar {{
        background: {p.bg};
        border-bottom: 1px solid {p.border};
    }}
    QLineEdit#search {{
        background: {p.surface};
        border: 1px solid {p.border};
        border-radius: 20px;
        padding: 8px 16px;
        color: {p.text};
        font-size: 14px;
        selection-background-color: {p.accent};
    }}
    QLineEdit#search:focus {{
        border-color: {p.accent};
    }}

    /* ── Cards ───────────────────────────────────────────────── */
    QFrame#card {{
        background: {p.surface};
        border: 1px solid {p.border};
        border-radius: 12px;
    }}
    QFrame#card:hover {{
        background: {p.surface_hover};
        border-color: {p.accent};
    }}

    QLabel#cardTitle {{
        color: {p.text};
        font-size: 14px;
        font-weight: 600;
    }}
    QLabel#cardMeta {{
        color: {p.text_dim};
        font-size: 12px;
    }}

    /* ── Headings ────────────────────────────────────────────── */
    QLabel#h1 {{ font-size: 28px; font-weight: 800; }}
    QLabel#h2 {{ font-size: 20px; font-weight: 700; }}
    QLabel#h3 {{ font-size: 16px; font-weight: 600; color: {p.text_muted}; }}
    QLabel#muted {{ color: {p.text_muted}; }}

    /* ── Buttons ─────────────────────────────────────────────── */
    QPushButton {{
        background: {p.surface};
        border: 1px solid {p.border};
        border-radius: 8px;
        padding: 8px 16px;
        color: {p.text};
        font-weight: 600;
    }}
    QPushButton:hover {{ background: {p.surface_hover}; border-color: {p.accent}; }}
    QPushButton:pressed {{ background: {p.bg_alt}; }}

    QPushButton[accent="true"] {{
        background: {p.accent};
        color: white;
        border: none;
    }}
    QPushButton[accent="true"]:hover {{ background: {p.accent_hover}; }}
    QPushButton[accent="true"]:pressed {{ background: {p.accent_pressed}; }}

    /* ── Lists ───────────────────────────────────────────────── */
    QListWidget, QTreeWidget {{
        background: {p.bg};
        border: none;
        outline: none;
    }}
    QListWidget::item {{ padding: 10px; border-radius: 8px; }}
    QListWidget::item:hover {{ background: {p.surface}; }}
    QListWidget::item:selected {{ background: {p.surface_hover}; color: {p.text}; }}

    /* ── Scrollbars ──────────────────────────────────────────── */
    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {p.border};
        border-radius: 5px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {p.text_dim}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar:horizontal {{ background: transparent; height: 10px; }}
    QScrollBar::handle:horizontal {{ background: {p.border}; border-radius: 5px; min-width: 30px; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

    /* ── ComboBox ────────────────────────────────────────────── */
    QComboBox {{
        background: {p.surface};
        border: 1px solid {p.border};
        border-radius: 6px;
        padding: 6px 10px;
        min-width: 80px;
    }}
    QComboBox:hover {{ border-color: {p.accent}; }}
    QComboBox QAbstractItemView {{
        background: {p.surface};
        border: 1px solid {p.border};
        selection-background-color: {p.accent};
    }}

    /* ── Progress ────────────────────────────────────────────── */
    QProgressBar {{
        background: {p.bg_alt};
        border: none;
        border-radius: 4px;
        text-align: center;
        height: 8px;
        color: transparent;
    }}
    QProgressBar::chunk {{ background: {p.accent}; border-radius: 4px; }}

    /* ── Snackbar ────────────────────────────────────────────── */
    #snackbar {{
        background: {p.surface_hover};
        border: 1px solid {p.border};
        border-left: 4px solid {p.accent};
        border-radius: 8px;
        padding: 10px 14px;
    }}
    #snackbar[level="error"] {{ border-left-color: {p.danger}; }}
    #snackbar[level="success"] {{ border-left-color: {p.success}; }}
    """
