from __future__ import annotations

from anisync.core.models import (
    AnimeSummary,
    DownloadStatus,
    Episode,
    HistoryEntry,
    ListKind,
    Subtitle,
    VideoSource,
)
from datetime import datetime


def test_video_source_height_parsing():
    v = VideoSource(url="x", quality="1080p")
    assert v.height == 1080
    assert VideoSource(url="x", quality="720p").height == 720
    assert VideoSource(url="x", quality="unknown").height == 0


def test_history_entry_progress():
    e = HistoryEntry(
        anime_url="x", provider_id="p", episode_number=1,
        position_seconds=300, duration_seconds=1200,
        watched_at=datetime.utcnow(),
    )
    assert 0.24 < e.progress < 0.26
    e2 = HistoryEntry(
        anime_url="x", provider_id="p", episode_number=1,
        position_seconds=0, duration_seconds=0,
        watched_at=datetime.utcnow(),
    )
    assert e2.progress == 0.0


def test_listkind_enum_values():
    assert ListKind.FAVORITE.value == "favorite"
    assert DownloadStatus.QUEUED.value == "queued"


def test_dataclasses_are_immutable():
    s = AnimeSummary(provider_id="p", url="u", title="t")
    try:
        s.title = "other"  # type: ignore[misc]
    except Exception:
        return
    raise AssertionError("AnimeSummary should be frozen")


def test_episode_construction():
    ep = Episode(
        provider_id="yummyanime",
        anime_url="vy-arestovany-1",
        number=1,
        title=None,
        embed_url="https://kodikplayer.com/x",
        dub="AniDUB",
        player_name="Kodik",
    )
    assert ep.number == 1
    assert "kodik" in ep.embed_url


def test_subtitle_default_format():
    s = Subtitle(url="x", lang="en")
    assert s.format == "vtt"
