# Architecture

Anisync is a layered, plugin-driven desktop app. Each layer has a single
responsibility and depends only on the layers below it.

```
┌─────────────────────────────────────────────────────────┐
│                       UI  (PySide6)                     │
│  Pages: Home · Search · Details · Player · Library ·    │
│         Downloads · Settings                            │
└───────────────────────▲─────────────────────────────────┘
                        │ signals / async tasks
┌───────────────────────┴─────────────────────────────────┐
│                 Core / Services                         │
│  registry · library (SQLite) · downloader · config      │
└───────────────────────▲─────────────────────────────────┘
                        │
┌───────────────────────┴─────────────────────────────────┐
│             Providers          │        Players        │
│  yummyanime, …                 │   kodik, aniboom, …   │
└─────────────────────────────────────────────────────────┘
                        │
┌───────────────────────┴─────────────────────────────────┐
│              Utils: http (httpx), paths, logging        │
└─────────────────────────────────────────────────────────┘
```

## Key abstractions

### `core.models`

Immutable dataclasses passed between layers:

- `AnimeSummary` — minimal info for grid cards (id, title, poster, year).
- `Anime` — full details (description, genres, episodes count, dubs, source url).
- `Episode` — `number`, `title`, `provider_id`, `embed_url`, `dub`.
- `VideoSource` — resolved playable stream: `url`, `quality`, `mime`,
  `headers`, optional `subtitles`.
- `DownloadTask` — persisted state for the downloader.

### `core.registry`

Two global registries discovered at import time:

- `provider_registry` — site scrapers implementing `BaseProvider`.
- `player_registry` — embedded-player resolvers implementing `BasePlayerResolver`.

Plugins register themselves with the `@register_provider` / `@register_player`
decorator. New plugins drop into `anisync/providers/` or `anisync/players/`
and are auto-imported by `anisync/providers/__init__.py`.

### `core.library`

SQLite database (`~/.anisync/library.db`). Tables:

- `users` — local-only for now; one row created on first launch.
- `anime_cache` — cached metadata so favorites/history survive site changes.
- `favorites` — per-user list memberships (PLANNING, WATCHING, COMPLETED, FAVORITE, DROPPED).
- `history` — `(user_id, anime_id, episode_number, position_seconds, watched_at)`.
- `downloads` — persistent download queue.

Access goes through `LibraryService` which exposes only high-level methods
(`add_favorite`, `mark_watched`, `list_history`, …) so the schema can evolve.

### `core.downloader`

Async download manager built on `yt-dlp` (handles HLS, MP4, Kodik, etc.) +
`httpx` for direct files. Concurrency limited via `asyncio.Semaphore`.
Emits Qt signals via a thin adapter (`ui.signals.DownloaderSignals`).

### `providers.base.BaseProvider`

```python
class BaseProvider(ABC):
    id: str
    display_name: str
    base_url: str

    async def search(self, query: str, limit: int = 20) -> list[AnimeSummary]: ...
    async def get_anime(self, anime_url: str) -> Anime: ...
    async def list_episodes(self, anime: Anime) -> list[Episode]: ...
```

The provider returns *embed URLs* — it does **not** know how to resolve a
stream. That is the player resolver's job, which keeps providers small.

### `players.base.BasePlayerResolver`

```python
class BasePlayerResolver(ABC):
    id: str
    def can_resolve(self, embed_url: str) -> bool: ...
    async def resolve(self, embed_url: str) -> list[VideoSource]: ...
```

The download manager and player both call
`player_registry.resolve(embed_url)` which dispatches to the first matching
resolver.

## Data flow — "Play episode" example

```
User clicks ▶ on Episode card
     │
     ▼
ui.pages.details → core.session.play(episode)
     │
     ▼
player_registry.resolve(episode.embed_url)
     │  ── kodik.KodikResolver.resolve() ──►  [VideoSource(…1080p), …]
     ▼
ui.pages.player loads best VideoSource into QMediaPlayer
     │
     ▼
library.record_history(user, episode, position)  (throttled every 5s)
```

## Threading & async

- UI runs on Qt main thread.
- All I/O (HTTP, scraping, DB writes) runs on a `QThreadPool`-backed
  executor via `utils.async_runner.run_async(coro)` which returns a
  `QFuture`-like signal object.
- `httpx.AsyncClient` is shared per-provider with sensible timeouts and a
  realistic `User-Agent` (`utils.http`).

## Error handling

- Network errors → typed exceptions in `core.errors` (`ProviderError`,
  `ResolveError`, `DownloadError`). UI shows a snackbar; nothing crashes.
- Scraping breakage → providers must raise `ProviderParseError` with the
  failing field so tests catch regressions early.

## Why these choices?

- **PySide6** — native look, true cross-platform, mature multimedia, no
  Electron-sized RAM cost, single language for scrapers + UI.
- **yt-dlp** — already supports Kodik / many anime hosts, battle-tested HLS.
- **SQLite via stdlib `sqlite3`** — zero deps, easy migrations.
- **Plugin registries** — adding a site/player must require **zero** changes
  to UI or core.

See [PROVIDERS.md](PROVIDERS.md) and [PLAYERS.md](PLAYERS.md) for the
concrete contracts when extending the app.
