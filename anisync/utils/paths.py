"""Per-user / per-app file paths, resolved via :mod:`platformdirs`."""
from __future__ import annotations

import re
from pathlib import Path

from platformdirs import user_data_dir, user_videos_dir

_APP = "Anisync"

_INVALID_FS_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def data_dir() -> Path:
    p = Path(user_data_dir(_APP, appauthor=False))
    p.mkdir(parents=True, exist_ok=True)
    return p


def cache_dir() -> Path:
    p = data_dir() / "cache"
    p.mkdir(parents=True, exist_ok=True)
    return p


def library_db_path() -> Path:
    return data_dir() / "library.db"


def config_path() -> Path:
    return data_dir() / "config.toml"


def default_downloads_dir() -> Path:
    p = Path(user_videos_dir()) / _APP
    return p


def safe_filename(name: str, *, max_length: int = 180) -> str:
    """Strip filesystem-invalid characters; never returns an empty string."""
    cleaned = _INVALID_FS_CHARS.sub(" ", name).strip().rstrip(".")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return (cleaned or "untitled")[:max_length]
