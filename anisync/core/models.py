"""Immutable data models passed between layers.

These dataclasses are the *only* shared vocabulary between providers,
players, the downloader, the library and the UI. Keep them small and
serializable (no Qt / no httpx objects).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _utcnow() -> datetime:
    """Naive UTC timestamp (utcnow() is deprecated from Python 3.12)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass(frozen=True, slots=True)
class AnimeSummary:
    """Minimal info shown in grid cards / search results."""
    provider_id: str
    url: str                # canonical URL on the provider site (acts as id)
    title: str
    poster_url: str | None = None
    year: int | None = None
    episodes_count: int | None = None
    type: str | None = None   # "TV", "Movie", "OVA", ...


@dataclass(frozen=True, slots=True)
class Anime:
    """Full anime details fetched from a provider."""
    provider_id: str
    url: str
    title: str
    original_title: str | None = None
    poster_url: str | None = None
    description: str = ""
    year: int | None = None
    type: str | None = None
    status: str | None = None        # "ongoing", "released", ...
    genres: tuple[str, ...] = ()
    studios: tuple[str, ...] = ()
    episodes_count: int | None = None
    dubs: tuple[str, ...] = ()       # available dubbings/voice-overs
    rating: float | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Episode:
    """One episode + its embed URL (player-agnostic)."""
    provider_id: str
    anime_url: str
    number: int
    title: str | None
    embed_url: str
    dub: str | None = None            # e.g. "AniDUB"
    player_name: str | None = None    # e.g. "kodik"
    duration: int | None = None       # seconds, if known


@dataclass(frozen=True, slots=True)
class Subtitle:
    url: str
    lang: str
    label: str | None = None
    format: str = "vtt"


@dataclass(frozen=True, slots=True)
class VideoSource:
    """Resolved playable stream returned by a player resolver."""
    url: str
    quality: str                       # "1080p", "720p", "480p", ...
    mime: str = "video/mp4"
    is_hls: bool = False
    headers: dict[str, str] = field(default_factory=dict)
    subtitles: tuple[Subtitle, ...] = ()

    @property
    def height(self) -> int:
        """Pixel height parsed from `quality` ("1080p" -> 1080)."""
        try:
            return int(self.quality.rstrip("pPi"))
        except ValueError:
            return 0


# ─── library entities ─────────────────────────────────────────────────────────


class ListKind(str, Enum):
    FAVORITE = "favorite"
    WATCHING = "watching"
    PLANNING = "planning"
    COMPLETED = "completed"
    DROPPED = "dropped"


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    anime_url: str
    provider_id: str
    episode_number: int
    position_seconds: int
    duration_seconds: int
    watched_at: datetime
    title: str = ""
    poster_url: str | None = None

    @property
    def progress(self) -> float:
        if self.duration_seconds <= 0:
            return 0.0
        return min(1.0, self.position_seconds / self.duration_seconds)


class DownloadStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


@dataclass(slots=True)
class DownloadTask:
    id: int
    provider_id: str
    anime_url: str
    anime_title: str
    episode_number: int
    embed_url: str
    quality: str
    file_path: str
    status: DownloadStatus = DownloadStatus.QUEUED
    progress: float = 0.0          # 0..1
    speed_bps: float = 0.0
    error: str | None = None
    created_at: datetime = field(default_factory=_utcnow)
