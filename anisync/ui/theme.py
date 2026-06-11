"""Apple TV / Crunchyroll inspired dark cinematic theme.

Design principles
-----------------
* **No chrome** — full-bleed dark background, content carries the colour.
* **Big typography** — SF Pro Display weights 300/600/800, generous spacing.
* **Subtle surfaces** — almost-black panels with a single 1 px hairline
  border, no heavy borders or rgba noise.
* **Single brand accent** — Crunchyroll orange ``#F47521`` reserved for
  primary CTAs and progress.
* **Cards live by their artwork** — poster cards have no background, the
  poster itself *is* the card. Focus state = scale + accent ring.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    # neutrals — Apple TV-style near-blacks
    bg:         str = "#000000"
    surface:    str = "#0E0E10"
    surface_2:  str = "#16161A"
    surface_3:  str = "#1F1F25"
    hairline:   str = "rgba(255,255,255,28)"
    hairline_2: str = "rgba(255,255,255,60)"

    # text
    text:       str = "#FFFFFF"
    text_muted: str = "#B4B4BE"
    text_dim:   str = "#6E6E78"

    # accents
    accent:         str = "#F47521"
    accent_hot:     str = "#FF8A3D"
    accent_press:   str = "#C95C12"
    accent_grad_to: str = "#FF4D6D"   # Crunchyroll-ish orange→red
    info:           str = "#5AC8FA"
    success:        str = "#34C759"
    danger:         str = "#FF453A"
    warning:        str = "#FFD60A"


PALETTE = Palette()


# Reusable QSS font stack — picks the best available system font on each
# platform. ".AppleSystemUIFont" is the real macOS system family alias and
# avoids the "SF Pro Display missing" warning Qt emits when it falls back.
FONT_FAMILY = (
    '".AppleSystemUIFont", "SF Pro Text", -apple-system, BlinkMacSystemFont, '
    '"Segoe UI Variable", "Segoe UI", "Inter", '
    '"Helvetica Neue", Arial, sans-serif'
)


def build_qss(p: Palette = PALETTE) -> str:
    return f"""
    * {{
        font-family: {FONT_FAMILY};
        color: {p.text};
        outline: none;
    }}

    QToolTip {{
        background: {p.surface_2};
        color: {p.text};
        border: 1px solid {p.hairline};
        padding: 6px 10px;
        border-radius: 8px;
    }}

    /* ── Root shell ───────────────────────────────────────────── */
    #root          {{ background: transparent; }}
    QMainWindow    {{ background: {p.bg}; }}
    QDialog        {{ background: {p.surface}; }}

    /* Release notes / changelog viewers */
    QTextBrowser#releaseNotes {{
        background: {p.surface_2};
        border: 1px solid {p.hairline};
        border-radius: 12px;
        padding: 12px;
        font-size: 13px;
    }}

    /* ── Top navigation bar ───────────────────────────────────── */
    #topnav {{
        background: rgba(8, 8, 10, 200);
        border: none;
        border-bottom: 1px solid {p.hairline};
    }}
    #topnav QLabel#wordmark {{
        color: {p.accent};
        font-size: 20px;
        font-weight: 800;
        letter-spacing: 2px;
    }}
    QPushButton.nav {{
        background: transparent;
        border: none;
        color: {p.text_muted};
        padding: 6px 14px;
        font-size: 14px;
        font-weight: 600;
        border-radius: 8px;
    }}
    QPushButton.nav:hover         {{ color: {p.text}; }}
    QPushButton.nav[active="true"]{{
        color: {p.text};
        background: rgba(255,255,255,18);
    }}

    /* macOS-style window buttons (only used on Win/Linux frameless) */
    QPushButton#winBtn {{
        background: rgba(255,255,255,30);
        border: none;
        border-radius: 6px;
        min-width: 12px; min-height: 12px;
        max-width: 12px; max-height: 12px;
        padding: 0;
    }}
    QPushButton#winBtn[role="close"] {{ background: #FF5F57; }}
    QPushButton#winBtn[role="min"]   {{ background: #FEBC2E; }}
    QPushButton#winBtn[role="max"]   {{ background: #28C840; }}

    /* ── Typography ───────────────────────────────────────────── */
    QLabel#display    {{ font-size: 56px; font-weight: 800; letter-spacing: -1.5px; }}
    QLabel#h1         {{ font-size: 34px; font-weight: 700; letter-spacing: -0.5px; }}
    QLabel#h2         {{ font-size: 22px; font-weight: 700; letter-spacing: -0.2px; }}
    QLabel#h3         {{ font-size: 16px; font-weight: 600; color: {p.text_muted}; }}
    QLabel#muted      {{ color: {p.text_muted}; font-size: 13px; }}
    QLabel#dim        {{ color: {p.text_dim};   font-size: 12px; }}
    QLabel#kicker     {{ color: {p.accent};     font-size: 12px; font-weight: 700;
                         letter-spacing: 2.5px; text-transform: uppercase; }}
    QLabel#cardTitle  {{ font-size: 13px; font-weight: 600; }}
    QLabel#cardMeta   {{ font-size: 11px; color: {p.text_dim}; }}

    /* ── Buttons ──────────────────────────────────────────────── */
    QPushButton {{
        background: rgba(255,255,255,14);
        border: 1px solid rgba(255,255,255,18);
        border-radius: 10px;
        padding: 9px 18px;
        color: {p.text};
        font-size: 13px;
        font-weight: 600;
    }}
    QPushButton:hover    {{ background: rgba(255,255,255,28); }}
    QPushButton:pressed  {{ background: rgba(255,255,255,10); }}
    QPushButton:disabled {{ color: {p.text_dim}; background: rgba(255,255,255,8); }}
    QPushButton:focus    {{ outline: none; }}

    /* Primary CTA. Both setObjectName("primary") and setProperty("accent", True) work. */
    QPushButton#primary, QPushButton[accent="true"] {{
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
            stop:0 {p.accent}, stop:1 {p.accent_grad_to});
        color: white;
        border: none;
        padding: 11px 24px;
        border-radius: 10px;
        font-weight: 700;
    }}
    QPushButton#primary:hover, QPushButton[accent="true"]:hover {{
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
            stop:0 {p.accent_hot}, stop:1 #FF6A86);
    }}
    QPushButton#primary:pressed, QPushButton[accent="true"]:pressed {{
        background: {p.accent_press};
    }}

    /* Ghost — invisible at rest, hint border on hover. */
    QPushButton#ghost, QPushButton[ghost="true"] {{
        background: transparent;
        border: 1px solid transparent;
        color: {p.text};
        padding: 9px 18px;
        border-radius: 10px;
    }}
    QPushButton#ghost:hover, QPushButton[ghost="true"]:hover {{
        background: rgba(255,255,255,12);
        border-color: {p.hairline};
    }}

    /* Outlined — visible thin border at rest. */
    QPushButton#outlined {{
        background: transparent;
        border: 1px solid {p.hairline_2};
        color: {p.text};
        padding: 9px 18px;
        border-radius: 10px;
    }}
    QPushButton#outlined:hover {{ background: rgba(255,255,255,14); }}
    QPushButton#outlined:checked {{
        background: {p.accent};
        border-color: {p.accent};
        color: white;
    }}

    QPushButton[icon="true"] {{
        background: rgba(0,0,0,140);
        border: 1px solid {p.hairline};
        border-radius: 20px;
        min-width: 40px; min-height: 40px;
        padding: 0;
        font-size: 16px;
    }}
    QPushButton[icon="true"]:hover {{ background: rgba(255,255,255,18); }}

    /* ── Carousel chevrons (kept invisible until hover) ──────── */
    QPushButton[chev="true"] {{
        background: rgba(0,0,0,180);
        border: 1px solid {p.hairline};
        border-radius: 24px;
        min-width: 48px; min-height: 48px;
        color: white;
        font-size: 20px;
        font-weight: 700;
    }}
    QPushButton[chev="true"]:hover {{ background: rgba(0,0,0,220); }}

    /* ── Poster card (no background — the poster IS the card) ─ */
    QFrame#poster {{
        background: transparent;
        border: none;
    }}
    QFrame#poster QLabel#posterImg {{
        background: {p.surface_2};
        border-radius: 10px;
    }}
    QFrame#poster[hovered="true"] QLabel#posterImg {{
        border: 2px solid {p.accent};
    }}

    /* ── Generic surfaces ────────────────────────────────────── */
    QFrame#card {{
        background: {p.surface};
        border: 1px solid {p.hairline};
        border-radius: 14px;
    }}
    QFrame#surface {{
        background: {p.surface_2};
        border: 1px solid {p.hairline};
        border-radius: 16px;
    }}

    /* ── Inputs ──────────────────────────────────────────────── */
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
        background: rgba(255,255,255,10);
        border: 1px solid transparent;
        border-radius: 10px;
        padding: 9px 14px;
        color: {p.text};
        font-size: 14px;
        selection-background-color: {p.accent};
    }}
    QLineEdit:hover, QComboBox:hover, QSpinBox:hover {{
        background: rgba(255,255,255,16);
    }}
    /* Accent ring only for text inputs — combos/spinners keep focus
       implicitly after their popup closes and would otherwise stay lit. */
    QLineEdit:focus {{
        border-color: {p.accent};
        background: rgba(255,255,255,16);
    }}
    QComboBox:focus, QSpinBox:focus {{ border-color: {p.hairline_2}; }}
    QLineEdit#search {{
        background: {p.surface};
        border: 1px solid {p.hairline_2};
        border-radius: 24px;
        padding: 12px 22px;
        font-size: 16px;
    }}
    QLineEdit#search:focus {{ border-color: {p.accent}; }}
    QLineEdit#searchBig {{
        background: transparent;
        border: none;
        border-bottom: 2px solid {p.hairline_2};
        border-radius: 0;
        padding: 14px 4px;
        font-size: 32px;
        font-weight: 300;
    }}
    QLineEdit#searchBig:focus {{ border-bottom-color: {p.accent}; }}
    QComboBox::drop-down {{ border: none; width: 18px; }}
    QComboBox QAbstractItemView {{
        background: {p.surface_2};
        border: 1px solid {p.hairline_2};
        border-radius: 10px;
        padding: 4px;
        selection-background-color: {p.accent};
    }}

    /* ── Scrollbars (slim like Apple TV / Crunchyroll) ─────── */
    QScrollBar:vertical {{ background: transparent; width: 8px; margin: 4px 2px; }}
    QScrollBar::handle:vertical {{
        background: rgba(255,255,255,50);
        border-radius: 4px;
        min-height: 28px;
    }}
    QScrollBar::handle:vertical:hover {{ background: rgba(255,255,255,90); }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
    QScrollBar:horizontal {{ background: transparent; height: 0px; }}

    /* ── Progress bars ───────────────────────────────────────── */
    QProgressBar {{
        background: rgba(255,255,255,18);
        border: none;
        border-radius: 3px;
        height: 6px;
        color: transparent;
    }}
    QProgressBar::chunk {{
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
            stop:0 {p.accent}, stop:1 {p.accent_grad_to});
        border-radius: 3px;
    }}

    /* ── Sliders (player) ────────────────────────────────────── */
    QSlider::groove:horizontal {{
        background: rgba(255,255,255,28);
        height: 4px; border-radius: 2px;
    }}
    QSlider::sub-page:horizontal {{ background: {p.accent}; border-radius: 2px; }}
    QSlider::handle:horizontal {{
        background: white; width: 14px; margin: -5px 0; border-radius: 7px;
    }}

    /* ── Snackbar ────────────────────────────────────────────── */
    #snackbar {{
        background: {p.surface_2};
        border: 1px solid {p.hairline_2};
        border-left: 4px solid {p.accent};
        border-radius: 12px;
        padding: 12px 16px;
    }}
    #snackbar[level="error"]   {{ border-left-color: {p.danger}; }}
    #snackbar[level="success"] {{ border-left-color: {p.success}; }}
    #snackbar[level="warning"] {{ border-left-color: {p.warning}; }}

    /* ── Player overlay gradient ─────────────────────────────── */
    #playerOverlay {{
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
            stop:0 rgba(0,0,0,200), stop:0.25 rgba(0,0,0,0),
            stop:0.75 rgba(0,0,0,0), stop:1 rgba(0,0,0,220));
    }}

    /* ── CheckBox ────────────────────────────────────────────── */
    QCheckBox {{ spacing: 8px; color: {p.text}; }}
    QCheckBox::indicator {{
        width: 18px; height: 18px;
        border: 1px solid {p.hairline_2};
        background: {p.surface};
        border-radius: 5px;
    }}
    QCheckBox::indicator:checked {{ background: {p.accent}; border-color: {p.accent}; }}
    """
