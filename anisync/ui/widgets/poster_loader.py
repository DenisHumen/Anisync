"""Async poster loader. Caches downloaded bytes in :func:`cache_dir`."""
from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path

import httpx
from PySide6.QtCore import QObject, Signal

from anisync.utils.async_runner import run_async
from anisync.utils.paths import cache_dir

log = logging.getLogger(__name__)

# Cap the on-disk poster cache. Without a limit it grows forever (every
# search result ever seen). Eviction is LRU: cache hits touch the file's
# mtime, pruning removes the oldest files first.
_CACHE_MAX_BYTES = 200 * 1024 * 1024


def _prune_cache(folder: Path) -> None:
    try:
        stats = [(f.stat(), f) for f in folder.iterdir() if f.is_file()]
    except OSError:
        return
    total = sum(st.st_size for st, _ in stats)
    if total <= _CACHE_MAX_BYTES:
        return
    # oldest-first; stop once we're comfortably under the cap
    for st, f in sorted(stats, key=lambda pair: pair[0].st_mtime):
        try:
            f.unlink()
        except OSError:
            continue
        total -= st.st_size
        if total <= _CACHE_MAX_BYTES * 0.8:
            break


class PosterLoader(QObject):
    loaded = Signal(bytes)  # raw image bytes

    def __init__(self, url: str | None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._url = url

    def start(self) -> None:
        if not self._url:
            return

        def _emit(b: bytes | None) -> None:
            # The owning widget may have been destroyed while the
            # request was in flight (e.g. user cleared a search grid).
            # Emitting a signal on a deleted C++ object raises
            # RuntimeError from shiboken — swallow it silently.
            try:
                self.loaded.emit(b or b"")
            except RuntimeError:
                pass

        run_async(_fetch(self._url), on_done=_emit)


async def _fetch(url: str) -> bytes:
    digest = hashlib.sha1(url.encode()).hexdigest()
    cache_file: Path = cache_dir() / "posters" / f"{digest}"
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    if cache_file.exists():
        try:
            os.utime(cache_file)  # refresh mtime → LRU "recently used"
        except OSError:
            pass
        return cache_file.read_bytes()
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(url, follow_redirects=True)
            r.raise_for_status()
            cache_file.write_bytes(r.content)
            _prune_cache(cache_file.parent)
            return r.content
    except Exception as e:  # noqa: BLE001
        log.warning("Poster fetch failed for %s: %s", url, e)
        return b""
