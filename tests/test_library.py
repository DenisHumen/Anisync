from __future__ import annotations

from anisync.core.models import (
    AnimeSummary,
    DownloadStatus,
    DownloadTask,
    ListKind,
)


def _summary(url="vy-arestovany-1") -> AnimeSummary:
    return AnimeSummary(
        provider_id="yummyanime", url=url, title="Vy Arestovany",
        poster_url="https://example/p.jpg", year=1996, episodes_count=47,
    )


def test_default_user_created(tmp_library):
    assert tmp_library.default_user_id > 0


def test_cache_and_retrieve(tmp_library):
    s = _summary()
    tmp_library.cache_anime(s)
    got = tmp_library.get_cached(s.provider_id, s.url)
    assert got is not None and got.title == s.title


def test_favorites_lifecycle(tmp_library):
    s = _summary()
    assert not tmp_library.is_in_list(s.provider_id, s.url, ListKind.FAVORITE)
    tmp_library.add_to_list(s, ListKind.FAVORITE)
    assert tmp_library.is_in_list(s.provider_id, s.url, ListKind.FAVORITE)
    listed = tmp_library.list_anime(ListKind.FAVORITE)
    assert any(x.url == s.url for x in listed)
    tmp_library.remove_from_list(s.provider_id, s.url, ListKind.FAVORITE)
    assert not tmp_library.is_in_list(s.provider_id, s.url, ListKind.FAVORITE)


def test_history_records_progress(tmp_library):
    s = _summary()
    tmp_library.cache_anime(s)
    tmp_library.record_progress(s.provider_id, s.url, 1, 100, 1400)
    tmp_library.record_progress(s.provider_id, s.url, 1, 250, 1400)
    tmp_library.record_progress(s.provider_id, s.url, 2, 30, 1400)

    history = tmp_library.list_history()
    assert len(history) == 2
    ep1 = [h for h in history if h.episode_number == 1][0]
    assert ep1.position_seconds == 250

    watched = tmp_library.episodes_watched(s.provider_id, s.url)
    assert watched == {1, 2}


def test_downloads_persist(tmp_library):
    task = DownloadTask(
        id=0, provider_id="yummyanime", anime_url="x", anime_title="X",
        episode_number=1, embed_url="https://k", quality="720p",
        file_path="/tmp/x.mp4",
    )
    tid = tmp_library.add_download(task)
    assert tid > 0
    task.status = DownloadStatus.COMPLETED
    task.progress = 1.0
    tmp_library.update_download(task)
    found = [t for t in tmp_library.list_downloads() if t.id == tid][0]
    assert found.status == DownloadStatus.COMPLETED
    assert found.progress == 1.0
    tmp_library.delete_download(tid)
    assert not [t for t in tmp_library.list_downloads() if t.id == tid]
