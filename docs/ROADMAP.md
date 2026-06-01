# Roadmap

Each phase is mergeable on its own.

## Phase 0 — Scaffold ✅
- [x] Package layout, `pyproject.toml`, deps pinned.
- [x] Docs: architecture, providers, players, downloader, UI, roadmap.
- [x] Pytest config + CI-friendly settings.

## Phase 1 — Core domain ✅
- [x] Dataclasses (`Anime`, `Episode`, `VideoSource`, `DownloadTask`, …).
- [x] Plugin registries (`provider_registry`, `player_registry`).
- [x] `LibraryService` with SQLite (favorites + history + downloads).
- [x] Config loader (`~/.anisync/config.toml`).

## Phase 2 — YummyAnime + Kodik ✅
- [x] `providers/yummyanime.py` — search, get_anime, list_episodes.
- [x] `players/kodik.py` — resolver via yt-dlp.
- [x] Fixture-based parser tests (no network).

## Phase 3 — Download manager ✅
- [x] yt-dlp wrapper with progress hook → Qt signals.
- [x] Persistent queue, pause/resume/cancel.
- [x] Settings: max concurrent, download dir.

## Phase 4 — UI shell ✅
- [x] Theme + main window with sidebar.
- [x] Home, Search, Details, Player, Library, History, Downloads, Settings.
- [x] Snackbar for errors.

## Phase 5 — Polish ✅
- [x] **macOS 26 glass UI** — frameless window, animated wallpaper, platform-aware titlebar.
- [x] **Type-ahead search** with debounced suggestion popup.
- [x] **Inline animated download button** on search cards.
- [x] **Grouped downloads** with poster previews + per-episode progress bars.
- [x] **Plex/Jellyfin-style player** with auto-hiding overlay and keyboard shortcuts.
- [x] **Auth scaffold** (`core/auth.py` + `ui/pages/auth.py`) — offline mode today, ready for remote backend.
- [x] **In-app updater** (`core/updater.py` + `ui/dialogs/update_dialog.py`) via GitHub Releases.
- [x] **GitHub Actions release pipeline** producing DMG / EXE / AppImage per tag.
- [ ] mpv backend for player (better codec support).
- [ ] Subtitle picker.
- [ ] Provider: Anilibria, Animevost.
- [ ] Player: Aniboom, Sibnet.
- [ ] Pre-download next episode automatically.
- [ ] Deploy real registration backend.

## Phase 6 — Stretch
- [ ] Schedule view (airing calendar).
- [ ] Discord rich presence.
- [ ] Plugin store / hot-reload providers.

## How to track progress

Update this file as part of every PR. Each completed checkbox should
have a corresponding test or screenshot referenced in the PR.
