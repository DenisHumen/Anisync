# Downloader

The downloader pre-fetches episodes for offline viewing. It is built on
`yt-dlp` (HLS/DASH/MP4 support) wrapped in an async task queue with Qt
signals for UI progress.

## Components

- `core.downloader.DownloadManager` — singleton, owns the queue.
- `core.downloader.DownloadTask` — dataclass + DB row.
- `ui.pages.downloads.DownloadsPage` — UI binding.

## States

`QUEUED → RUNNING → COMPLETED | FAILED | PAUSED | CANCELED`

State transitions persist to SQLite so an interrupted app resumes the
queue on next launch.

## File layout

```
~/Movies/Anisync/
  └── <Anime Title>/
        └── S01E07 — Episode title [1080p].mp4
```

The path is configurable in Settings. File names are sanitized via
`utils.paths.safe_filename`.

## API

```python
mgr = DownloadManager.instance()
task_id = await mgr.enqueue(episode, quality="1080p")
mgr.pause(task_id)
mgr.resume(task_id)
mgr.cancel(task_id)
mgr.signals.progress.connect(lambda tid, pct, speed: ...)
```

## Concurrency

Default 2 simultaneous downloads (configurable). Per-task yt-dlp runs in
a worker thread; progress hook posts to the asyncio loop which emits
Qt signals on the UI thread.

## Future

- Resume partial HLS via `--continue` + segment cache.
- Bandwidth limiter.
- Auto-download next-episode queue.
