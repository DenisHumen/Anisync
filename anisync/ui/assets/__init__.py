"""Bundled UI assets (app logo, etc.)."""
from __future__ import annotations

from pathlib import Path


def logo_path() -> Path:
    """Absolute path to the app logo PNG (works in dev and frozen builds)."""
    return Path(__file__).resolve().parent / "logo.png"
