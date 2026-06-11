<div align="center">

<img src="packaging/anisync_mark.png" width="96" alt="Anisync logo" />

# Anisync

**A beautiful cross-platform desktop app for discovering, streaming and downloading anime.**

[![Latest release](https://img.shields.io/github/v/release/DenisHumen/Anisync?color=F47521&label=release)](https://github.com/DenisHumen/Anisync/releases/latest)
[![Build](https://github.com/DenisHumen/Anisync/actions/workflows/release.yml/badge.svg)](https://github.com/DenisHumen/Anisync/actions/workflows/release.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Qt / PySide6](https://img.shields.io/badge/UI-PySide6%20(Qt%206)-41CD52?logo=qt&logoColor=white)](https://doc.qt.io/qtforpython/)
[![Platforms](https://img.shields.io/badge/platforms-Windows%20%C2%B7%20macOS%20%C2%B7%20Linux-lightgrey)](#-installation)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

*Apple TV / Crunchyroll-inspired dark UI · embedded mpv player · modular provider system*

</div>

---

## ✨ Features

- 🎬 **In-app playback** — embedded **libmpv** rendered into a Qt OpenGL surface: HLS/DASH, hardware decoding, custom headers, every codec. No external player needed.
- 🔍 **Live search** across all providers — debounced as-you-type results, provider filter chips, `Ctrl+F` from anywhere.
- 📥 **Download manager** — persistent queue (survives restarts), per-episode + per-anime progress, speed display, cancel/retry, configurable concurrency and quality.
- 📚 **Library** — favorites, Watching/Planning/Completed/Dropped lists and full watch history with resume positions, stored locally in SQLite.
- 🔄 **Auto-updates** — checks GitHub Releases on startup, shows the changelog of every version you missed, downloads with live progress and installs in place. Full release history in *Settings → About → What's new*.
- 🧩 **Modular by design** — any anime site is a provider plugin, any embed player is a resolver plugin. Adding a source touches zero core code.
- 🖥️ **Truly cross-platform** — one codebase, native-feeling on Windows, macOS and Linux (X11/Wayland). Icons are drawn with QPainter, so the UI never depends on platform fonts.
- 🌙 **Cinematic dark UI** — frameless window, poster-first cards, smooth page transitions and hover animations, single orange accent.

## 📦 Installation

Grab the latest build from **[Releases](https://github.com/DenisHumen/Anisync/releases/latest)** — fully self-contained, nothing else to install.

| Platform | File | Notes |
|---|---|---|
| **Windows** | `Anisync-X.Y.Z-win.zip` | Unzip anywhere, run `Anisync.exe`. SmartScreen: *More info → Run anyway* (unsigned build). |
| **macOS** | `Anisync-X.Y.Z-mac.dmg` | Drag to Applications. First launch: right-click → **Open** (ad-hoc signed). |
| **Linux** | `Anisync-X.Y.Z.AppImage` | `chmod +x Anisync-*.AppImage && ./Anisync-*.AppImage` |

Once installed, Anisync keeps itself up to date — when a new version is published you'll get a prompt with the full changelog and a one-click **Install update**.

### Run from source

```bash
# Python 3.11+
git clone https://github.com/DenisHumen/Anisync.git
cd Anisync
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

python -m anisync                  # launch the GUI
pytest -q                          # run the test suite (offline)
```

For in-app playback a native **libmpv** is required in dev runs
(packaged builds bundle it):

| OS | How |
|---|---|
| macOS | `brew install mpv` |
| Debian/Ubuntu | `sudo apt install libmpv2` (or `libmpv1`) |
| Windows | put `libmpv-2.dll` ([mpv-dev builds](https://github.com/zhongfly/mpv-winbuild/releases)) on `PATH` |

## ⌨️ Keyboard shortcuts

| Key | Action |
|---|---|
| `Space` | Play / pause |
| `←` / `→` | Seek −10 s / +10 s |
| `Shift+←` / `Shift+→` | Seek −60 s / +60 s |
| `↑` / `↓` | Volume |
| `M` | Mute |
| `F` | Toggle fullscreen |
| `Esc` | Exit fullscreen |
| `Ctrl+F` / `Cmd+F` | Jump to search |

## 🏗 Architecture

```
anisync/
├── core/        # models, plugin registries, SQLite library, config,
│                # download manager, GitHub updater + self-update
├── providers/   # site scrapers — one module per source (yummyanime, …)
├── players/     # embed resolvers — one module per player (kodik, …)
├── ui/          # PySide6 pages, widgets, dialogs, QPainter icons, theme
└── utils/       # async runner, http client factory, paths, mpv loader
tests/           # pytest suite — fully offline by default
docs/            # design docs for humans & agents
```

Three rules hold everything together:

1. **Plain dataclasses cross layers** (`core/models.py`) — no Qt or httpx
   objects leak between UI, providers and the downloader.
2. **Plugins self-register** — dropping a file into `providers/` or
   `players/` is the whole integration (`@register_provider` /
   `@register_player`).
3. **The UI never blocks** — all I/O runs on a persistent asyncio loop in
   a worker thread (`utils/async_runner.run_async`), results come back
   through Qt signals.

### Adding a provider

```python
# anisync/providers/mysource.py
from anisync.core.registry import register_provider
from anisync.providers.base import BaseProvider

@register_provider
class MySourceProvider(BaseProvider):
    id = "mysource"
    display_name = "MySource"
    base_url = "https://example.com"

    async def search(self, query, *, limit=20): ...
    async def get_anime(self, anime_url): ...
    async def list_episodes(self, anime): ...
```

That's it — search, details, playback and downloads pick it up
automatically. See [docs/PROVIDERS.md](docs/PROVIDERS.md) and
[docs/PLAYERS.md](docs/PLAYERS.md) for the full contracts.

## 🔄 How updates work

1. On startup (and on demand from *Settings → About*) Anisync queries the
   GitHub Releases API.
2. If a newer version exists you get a dialog with the **combined release
   notes of every version you missed** — dates and notes come straight
   from the release descriptions on GitHub.
3. *Install update* downloads the platform asset with live progress, then
   a tiny helper swaps the build and relaunches the app. Dev runs get an
   *Open installer* fallback instead.
4. Releases are produced by [CI](.github/workflows/release.yml) on every
   `v*` tag — per-version notes live in
   [`.github/releases/`](.github/releases/). See
   [docs/UPDATER.md](docs/UPDATER.md) and
   [docs/RELEASES.md](docs/RELEASES.md).

## 📚 Documentation

| Document | Purpose |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | High-level design, layers, data flow |
| [docs/PROVIDERS.md](docs/PROVIDERS.md) | How to add a new anime source |
| [docs/PLAYERS.md](docs/PLAYERS.md) | How to add a new embed resolver |
| [docs/DOWNLOADER.md](docs/DOWNLOADER.md) | Download manager design |
| [docs/UI.md](docs/UI.md) | UI structure, theming, cross-platform rules |
| [docs/UPDATER.md](docs/UPDATER.md) | Auto-update system |
| [docs/RELEASES.md](docs/RELEASES.md) | Release engineering / CI pipeline |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Phased plan and progress |
| [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) | Developer / agent workflow |

## 🛠 Development

```bash
pip install -e ".[dev]"
pytest -q                       # offline suite
pytest -m live                  # live network tests (optional)
python -m compileall anisync    # quick syntax gate
```

Ground rules (the longer list lives in
[docs/CONTRIBUTING.md](docs/CONTRIBUTING.md)):

- style via theme tokens — no hardcoded colors in widgets;
- icons are QPainter-drawn (`ui/widgets/icons.py`) — never unicode
  glyphs/emoji, they break on Linux fonts;
- every page must stay responsive from 1024 px up;
- all I/O through `run_async` — never block the Qt event loop.

## ⚖️ License & disclaimer

[MIT](LICENSE). Anisync is a personal/educational project: it ships no
content and hosts nothing — it only embeds what source sites publicly
serve. Respect the Terms of Service of the sources you use and support
official releases where available.
