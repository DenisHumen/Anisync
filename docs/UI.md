# UI

PySide6 (Qt 6) with an **Apple TV / Crunchyroll-inspired dark cinematic**
look — frameless window, near-black surfaces, a single orange accent,
poster-first cards. The top navigation strip doubles as the titlebar
(traffic lights on macOS, drawn window buttons on Windows / Linux).

Layout: `TopNav` pinned at the top + a `QStackedWidget` of pages, all
sitting on top of `CinemaBackground`
(see [`anisync/ui/glass.py`](../anisync/ui/glass.py)) — a static
near-black backdrop with two corner glows.

## Page map

| Page | Module | Purpose |
|---|---|---|
| Home | `ui/pages/home.py` | Hero banner (Play = autoplay first episode) + Continue Watching / Trending / Fresh carousels |
| Search | `ui/pages/search.py` | Debounced live search, provider filter chips, responsive poster grid |
| Details | `ui/pages/details.py` | Hero with poster/synopsis, episode tiles grouped by dub, favorites/watching toggles |
| Player | `ui/pages/player.py` | Embedded libmpv, Plex-style overlay (auto-hide in fullscreen), quality/dub/episode switchers, full keyboard control |
| Library | `ui/pages/library.py` | Favorites + lists (Watching, Planning, …) as a responsive grid |
| History | `ui/pages/history.py` | Recently watched episodes with progress bars |
| Downloads | `ui/pages/downloads.py` | Grouped by anime, per-episode + aggregate progress, cancel/retry/open |
| Account | `ui/pages/auth.py` | Sign-in / register form, offline-mode banner |
| Settings | `ui/pages/settings.py` | Download path, concurrency, preferred quality/dub |

## Widgets

- `widgets/topnav.py` — nav strip / titlebar; window drag + controls.
- `widgets/anime_card.py` — `PosterCard`: poster-is-the-card tile with
  hover scale + accent ring.
- `widgets/carousel.py` — horizontal poster rail with animated paging
  chevrons.
- `widgets/icons.py` — QPainter-drawn monochrome icons (play, pause,
  skip ±10, prev/next, fullscreen, back, volume, window controls).
  **Use these instead of unicode glyphs / emoji** — media glyphs render
  as tofu boxes with the default Linux fonts.
- `widgets/poster_loader.py` — async poster fetch with an LRU on-disk
  cache (capped at ~200 MB).
- `widgets/snackbar.py` — bottom toast for non-blocking messages.
- `widgets/spinner.py` — QPainter spinner + `LoadingPanel`.

## Theme

`ui/theme.py` exports `build_qss(palette)` and a `Palette` dataclass.

* Primary accent: `#F47521` (Crunchyroll orange), gradient to `#FF4D6D`
  for primary CTAs and progress bars.
* Background: pure black; surfaces `#0E0E10 / #16161A / #1F1F25` with a
  1 px white hairline border.
* Typography: system font stack (SF Pro on macOS, Segoe UI on Windows,
  Inter/DejaVu fallback on Linux); object names `display/h1/h2/h3/
  kicker/muted/dim` select sizes.

Button variants are selected via object names or dynamic properties:

```python
btn.setObjectName("primary")      # orange gradient pill (or property accent=True)
btn.setObjectName("outlined")     # thin visible border
btn.setProperty("ghost", True)    # invisible at rest
btn.setProperty("icon",  True)    # circular 40 px icon button
```

To re-theme, edit `theme.py` and the glow colours in `glass.py` —
widgets must not hardcode colors.

## Cross-platform notes

* The window is frameless (`FramelessWindowHint`) but **opaque** — do
  not re-add `WA_TranslucentBackground`: per-pixel translucency buys
  nothing on this full-bleed black design and is a known source of
  compositing bugs with the embedded `QOpenGLWidget` video surface
  (Windows DWM) and broken decorations on Wayland. Dragging is handled
  by `TopNav`, edge-resize by an event filter in `MainWindow`.
* Never rely on fonts shipping media/dingbat glyphs; draw icons via
  `widgets/icons.py`.
* Paths, config and cache locations come from `utils/paths.py`
  (platformdirs) — never hardcode OS paths.

## Async UI

UI calls into core via `utils.async_runner.run_async(coro, on_done, on_error)`
which runs the coroutine on a persistent background asyncio loop and
marshals results back through Qt signals — never block the event loop.

## Adding a new page

1. Create `ui/pages/myfeature.py` with a `QWidget` subclass.
2. Register it in `ui/main_window.py`: add to `NAV_ITEMS` (if it should
   appear in the nav), `self._page_keys`, and `self._refreshers` (if it
   has a `refresh()`), then wire its signals.
3. Style only via theme tokens — no hardcoded colors.
