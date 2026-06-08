"""Async download manager built on top of yt-dlp.

Design notes
------------

* One :class:`DownloadManager` per app (singleton via :func:`get_manager`).
* Tasks are persisted in the SQLite library so an interrupted app resumes
  on next launch.
* yt-dlp runs in a worker thread (it is synchronous). A progress hook
  posts updates to the asyncio loop which emits Qt signals on the UI
  thread.
* Concurrency is bounded by :class:`asyncio.Semaphore` whose value comes
  from :class:`anisync.core.config.Config.max_concurrent_downloads`.

The manager is UI-framework-agnostic — it emits via Qt ``Signal`` only
because that is convenient. UI consumers connect and react. Headless
consumers can subscribe via :attr:`DownloadManager.signals`.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal

from anisync.core.config import Config
from anisync.core.errors import DownloadError, ResolveError
from anisync.core.library import LibraryService, get_library
from anisync.core.models import (
    DownloadStatus,
    DownloadTask,
    Episode,
    VideoSource,
)
from anisync.core.registry import resolve_for
from anisync.utils.paths import safe_filename

log = logging.getLogger(__name__)


class DownloaderSignals(QObject):
    enqueued = Signal(object)        # DownloadTask
    started = Signal(int)            # task_id
    progress = Signal(int, float, float)  # task_id, percent (0..1), speed bps
    completed = Signal(int)
    failed = Signal(int, str)
    canceled = Signal(int)


class DownloadManager:
    def __init__(
        self,
        *,
        config: Config | None = None,
        library: LibraryService | None = None,
    ) -> None:
        self._cfg = config or Config.load()
        self._lib = library or get_library()
        self.signals = DownloaderSignals()
        self._sem = asyncio.Semaphore(self._cfg.max_concurrent_downloads)
        self._tasks: dict[int, asyncio.Task[Any]] = {}
        self._canceled: set[int] = set()

    # ─── public API ───────────────────────────────────────────────────────

    async def enqueue(
        self,
        episode: Episode,
        anime_title: str,
        *,
        quality: str | None = None,
    ) -> DownloadTask:
        quality = quality or self._cfg.preferred_quality
        out_dir = Path(self._cfg.downloads_dir) / safe_filename(anime_title)
        out_dir.mkdir(parents=True, exist_ok=True)
        fname = safe_filename(
            f"E{episode.number:02d} - {episode.title or 'episode'} [{quality}].mp4"
        )
        task = DownloadTask(
            id=0,
            provider_id=episode.provider_id,
            anime_url=episode.anime_url,
            anime_title=anime_title,
            episode_number=episode.number,
            embed_url=episode.embed_url,
            quality=quality,
            file_path=str(out_dir / fname),
            status=DownloadStatus.QUEUED,
        )
        self._lib.add_download(task)
        self.signals.enqueued.emit(task)
        async_task = asyncio.create_task(self._run(task))
        self._tasks[task.id] = async_task
        return task

    def cancel(self, task_id: int) -> None:
        self._canceled.add(task_id)
        t = self._tasks.get(task_id)
        if t:
            t.cancel()

    def reload_config(self) -> None:
        """Adopt preferences (downloads dir, quality, concurrency) changed
        while the app is running. New downloads use the new values; tasks
        already in flight keep the slot they acquired."""
        self._cfg = Config.load()
        self._sem = asyncio.Semaphore(self._cfg.max_concurrent_downloads)

    async def resume_pending(self) -> int:
        """Re-queue downloads left unfinished by a previous run — QUEUED
        tasks and RUNNING ones interrupted by a crash/quit. Call once at
        startup. Returns the number of tasks resumed."""
        resumed = 0
        for task in self._lib.list_downloads():
            if task.status not in (DownloadStatus.QUEUED, DownloadStatus.RUNNING):
                continue
            if task.id in self._tasks:
                continue
            self._mark(task, DownloadStatus.QUEUED)
            self._tasks[task.id] = asyncio.create_task(self._run(task))
            resumed += 1
        return resumed

    # ─── core ─────────────────────────────────────────────────────────────

    async def _run(self, task: DownloadTask) -> None:
        async with self._sem:
            if task.id in self._canceled:
                self._mark(task, DownloadStatus.CANCELED)
                self.signals.canceled.emit(task.id)
                return
            try:
                self._mark(task, DownloadStatus.RUNNING)
                self.signals.started.emit(task.id)
                source = await self._pick_source(task)
                await self._download(task, source)
                self._mark(task, DownloadStatus.COMPLETED, progress=1.0)
                self.signals.completed.emit(task.id)
            except asyncio.CancelledError:
                self._mark(task, DownloadStatus.CANCELED)
                self.signals.canceled.emit(task.id)
            except Exception as e:  # noqa: BLE001
                log.exception("Download %s failed", task.id)
                self._mark(task, DownloadStatus.FAILED, error=str(e))
                self.signals.failed.emit(task.id, str(e))
            finally:
                self._tasks.pop(task.id, None)

    async def _pick_source(self, task: DownloadTask) -> VideoSource:
        resolver = resolve_for(task.embed_url)
        if resolver is None:
            raise DownloadError(f"No resolver for embed URL: {task.embed_url}")
        try:
            sources = await resolver.resolve(task.embed_url)
        except ResolveError as e:
            raise DownloadError(str(e)) from e
        if not sources:
            raise DownloadError("Resolver returned zero sources")
        # "best/max/auto" => pick the highest available (resolver already
        # returns sources sorted highest-first, but we sort defensively).
        sources_by_height = sorted(sources, key=lambda s: s.height, reverse=True)
        if task.quality.lower() in {"best", "max", "auto", ""}:
            return sources_by_height[0]
        try:
            target = int(task.quality.rstrip("pPi"))
        except ValueError:
            return sources_by_height[0]
        return min(sources_by_height, key=lambda s: abs(s.height - target))

    async def _download(self, task: DownloadTask, source: VideoSource) -> None:
        loop = asyncio.get_running_loop()

        def hook(d: dict[str, Any]) -> None:
            if d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                done = d.get("downloaded_bytes") or 0
                pct = (done / total) if total else 0.0
                speed = d.get("speed") or 0.0
                loop.call_soon_threadsafe(
                    self.signals.progress.emit, task.id, pct, float(speed)
                )

        from yt_dlp import YoutubeDL

        opts = {
            "outtmpl": task.file_path,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "progress_hooks": [hook],
            "http_headers": source.headers or {},
            "concurrent_fragment_downloads": 4,
        }

        def _go() -> None:
            with YoutubeDL(opts) as ydl:
                ydl.download([source.url])

        await loop.run_in_executor(None, _go)

    def _mark(
        self,
        task: DownloadTask,
        status: DownloadStatus,
        *,
        progress: float | None = None,
        error: str | None = None,
    ) -> None:
        task.status = status
        if progress is not None:
            task.progress = progress
        if error is not None:
            task.error = error
        self._lib.update_download(task)


_singleton: DownloadManager | None = None


def get_manager() -> DownloadManager:
    global _singleton
    if _singleton is None:
        _singleton = DownloadManager()
    return _singleton
