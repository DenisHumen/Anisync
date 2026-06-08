"""DownloadManager: live config reload + resume of interrupted downloads."""
from __future__ import annotations

import asyncio

import pytest

import anisync.core.config as config_mod
from anisync.core.config import Config
from anisync.core.downloader import DownloadManager
from anisync.core.models import DownloadStatus, DownloadTask


def _task(status: DownloadStatus, **over) -> DownloadTask:
    base = dict(
        id=0, provider_id="p", anime_url="a", anime_title="t",
        episode_number=1, embed_url="e", quality="best",
        file_path="/tmp/x.mp4", status=status,
    )
    base.update(over)
    return DownloadTask(**base)


def test_reload_config_adopts_saved_changes(tmp_path, monkeypatch, tmp_library):
    cfgfile = tmp_path / "config.toml"
    monkeypatch.setattr(config_mod, "config_path", lambda: cfgfile)

    mgr = DownloadManager(
        config=Config(max_concurrent_downloads=2, preferred_quality="best"),
        library=tmp_library,
    )
    assert mgr._sem._value == 2

    # Simulate the Settings page saving new preferences.
    Config(max_concurrent_downloads=5, preferred_quality="720p").save()
    mgr.reload_config()

    assert mgr._cfg.max_concurrent_downloads == 5
    assert mgr._cfg.preferred_quality == "720p"
    assert mgr._sem._value == 5


async def test_resume_pending_requeues_only_unfinished(tmp_library, monkeypatch):
    running = _task(DownloadStatus.RUNNING, progress=0.4)
    queued = _task(DownloadStatus.QUEUED)
    done = _task(DownloadStatus.COMPLETED, progress=1.0)
    failed = _task(DownloadStatus.FAILED, error="boom")
    for t in (running, queued, done, failed):
        tmp_library.add_download(t)

    mgr = DownloadManager(config=Config(), library=tmp_library)

    started: list[int] = []

    async def fake_run(task: DownloadTask) -> None:
        started.append(task.id)

    monkeypatch.setattr(mgr, "_run", fake_run)

    resumed = await mgr.resume_pending()
    await asyncio.gather(*mgr._tasks.values())

    assert resumed == 2
    assert sorted(started) == sorted([running.id, queued.id])

    # The interrupted RUNNING row is reset to QUEUED; finished rows untouched.
    by_id = {t.id: t for t in tmp_library.list_downloads()}
    assert by_id[running.id].status == DownloadStatus.QUEUED
    assert by_id[queued.id].status == DownloadStatus.QUEUED
    assert by_id[done.id].status == DownloadStatus.COMPLETED
    assert by_id[failed.id].status == DownloadStatus.FAILED


async def test_resume_pending_skips_already_running(tmp_library, monkeypatch):
    queued = _task(DownloadStatus.QUEUED)
    tmp_library.add_download(queued)
    mgr = DownloadManager(config=Config(), library=tmp_library)

    async def fake_run(task: DownloadTask) -> None:
        await asyncio.sleep(0.05)

    monkeypatch.setattr(mgr, "_run", fake_run)

    first = await mgr.resume_pending()
    second = await mgr.resume_pending()  # already in-flight → skipped
    await asyncio.gather(*mgr._tasks.values())

    assert first == 1
    assert second == 0
