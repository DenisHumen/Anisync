# UI

PySide6 (Qt 6) with a custom **macOS 26 glass** stylesheet — frameless
window, animated coloured-blob wallpaper, semi-transparent panels and a
platform-aware titlebar (traffic lights on macOS, conventional buttons
on Windows / Linux).

Layout: persistent left sidebar + stacked main content area, all sitting
on top of `WallpaperWidget` (see [`anisync/ui/glass.py`](../anisync/ui/glass.py)).

## Page map

| Page | Module | Purpose |
|---|---|---|
| Home | `ui/pages/home.py` | Hero banner + "Continue watching" rail |
| Search | `ui/pages/search.py` | Live type-ahead suggestions + wide result cards with inline download progress |
| Details | `ui/pages/details.py` | Poster, synopsis, dub picker, episode grid |
| Player | `ui/pages/player.py` | Plex/Jellyfin-style overlay, auto-hide on idle, full keyboard control |
| Library | `ui/pages/library.py` | Favorites + custom lists (WATCHING, PLANNING, …) |
| History | `ui/pages/history.py` | Recently watched episodes with resume |
| Downloads | `ui/pages/downloads.py` | Grouped by anime, per-episode + aggregate progress |
| Account | `ui/pages/auth.py` | Sign-in / register form, offline-mode banner |
| Settings | `ui/pages/settings.py` | Download path, concurrency, theme, update prefs |

## Widgets

- `widgets/sidebar.py` — animated nav, active-state highlight.
- `widgets/anime_card.py` — poster + hover overlay + favorite star.
- `widgets/episode_list.py` — scrollable list with watched-state pill.
- `widgets/snackbar.py` — bottom toast for non-blocking errors.

## Theme

`ui/theme.py` exports the QSS string and a `Palette` dataclass with
**rgba glass tokens** (`glass`, `glass_strong`, `glass_hover`, `border`).

* Primary accent: `#F47521` (Crunchyroll orange) gradient to `#FF9B5C`.
* Secondary accent: `#5AC8FA` (macOS blue) for progress bars.
* Background: `#08080F` painted by `WallpaperWidget` with three
  drifting `QRadialGradient` blobs.
* Surfaces: `rgba(28,28,38,160)` glass cards + 1 px white inner border
  + 30 px drop shadow via `anisync.ui.glass.apply_shadow(...)`.

Button variants are selected via Qt dynamic properties:

```python
btn.setProperty("accent", True)   # orange gradient pill
btn.setProperty("ghost",  True)   # outlined transparent
btn.setProperty("icon",   True)   # circular 36 px icon button
```

To re-theme, edit `theme.py` and the wallpaper colours in `glass.py` —
every widget pulls colors from there.

## Cross-platform glass

True OS blur (NSVisualEffectView / DWM acrylic) would need per-OS
native bindings, so Anisync ships a **portable approximation**:

1. `MainWindow` is `Qt.FramelessWindowHint | WA_TranslucentBackground`.
2. `WallpaperWidget` paints animated coloured blobs at the back.
3. Every panel is rgba-translucent so the colour bleeds through.
4. Soft drop shadow + 1 px inner border gives the *frosted* feel.

This works identically on macOS, Windows and Linux (KDE / GNOME, both
Wayland and X11) without any conditional code paths.

## Async UI

UI calls into core via `utils.async_runner.run_async(coro, on_done, on_error)`
which runs the coroutine on a background thread and marshals results back
through Qt signals — never block the event loop.

## Adding a new page

1. Create `ui/pages/myfeature.py` with a `QWidget` subclass.
2. Register in `ui/main_window.py`:
   ```python
   self._add_page("My Feature", "icon.svg", MyFeaturePage())
   ```
3. Style only via theme tokens — no hardcoded colors.
