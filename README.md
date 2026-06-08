# Anisync

A beautiful, modular desktop application for discovering, streaming and
downloading anime from multiple sources — inspired by Crunchyroll.

> Status: **MVP / alpha**. Built for further extension by other agents.
> All design decisions are documented in [`docs/`](docs/).

## Highlights

- **Crunchyroll-inspired dark UI** built with PySide6 (Qt 6).
- **Modular provider system** — any anime site is a plugin (`anisync/providers/`).
- **Modular player resolver system** — Kodik, Aniboom, etc. plug in independently
  (`anisync/players/`).
- **First provider:** [`YummyAnime`](https://old.yummyani.me) (Kodik player).
- **In-app playback** via embedded **mpv** (libmpv) rendered into a Qt
  OpenGL surface — HLS/DASH, hardware decoding, custom headers.
- **Downloader** — queue, pause/resume, progress, pre-download for offline viewing.
- **Library** (SQLite) — favorites, watch history, custom lists.
- **Search across providers** with a unified result page.
- **Account scaffolding** — local user model ready for future sync.

## Quick start

```bash
# Python 3.11+ required.
# Native libmpv is needed for in-app playback:
#   macOS:         brew install mpv
#   Debian/Ubuntu: sudo apt install libmpv2   (or libmpv1)
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Launch the GUI
python -m anisync

# Run tests
pytest -q
```

> Tip: `./run.sh` bootstraps the venv, self-heals a broken PySide6 install
> and launches the app in one step.

## Documentation

| Document | Purpose |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | High-level design, layers, data flow |
| [docs/PROVIDERS.md](docs/PROVIDERS.md) | How to add a new anime source |
| [docs/PLAYERS.md](docs/PLAYERS.md) | How to add a new embedded player resolver |
| [docs/DOWNLOADER.md](docs/DOWNLOADER.md) | Download manager design |
| [docs/UI.md](docs/UI.md) | UI structure, theming, page map |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Phased plan and current progress |
| [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) | Agent / developer workflow |

## Project layout

```
anisync/
├── core/        # models, registries, library, config, downloader
├── providers/   # site-specific scrapers (yummyanime, ...)
├── players/     # embedded player resolvers (kodik, ...)
├── ui/          # PySide6 pages, widgets, theme
└── utils/       # http, paths, logging
tests/           # pytest suite (no-network by default)
docs/            # design docs for humans & agents
```

## License

Personal/educational use. Respect the source sites' Terms of Service.

