# Updater

Anisync polls **GitHub Releases** at startup (unless disabled in
`Config.check_updates_on_start` / Settings → Updates) and offers a
yes/no update prompt when a newer version exists. Release notes come
straight from the GitHub release bodies, so the changelog the user sees
is whatever you write in the release description.

## Flow

1. `MainWindow.__init__` calls `UpdateService(cfg.update_repo).check_with_news()`
   via `run_async(...)`.
2. `check_with_news()` GETs `/repos/{repo}/releases` (drafts and
   prereleases skipped) and returns the newest release **plus every
   release newer than the running version** — the dialog shows the
   combined "what you missed" changelog with per-version dates. If the
   list endpoint is unavailable it falls back to `/releases/latest`.
3. `UpdateDialog` ("Install update" / "Later"):
   - downloads the platform asset with **live progress** (MB done/total)
     into `<data_dir>/updates/` — streamed to `*.part`, renamed when
     complete so an interrupted download never looks like an installer;
   - **packaged builds** (`selfupdate.can_self_update()`): the asset is
     staged (`selfupdate.stage`) and a detached helper swaps the build
     and relaunches (`selfupdate.apply_and_relaunch`) — fully automatic;
   - **dev runs / non-writable installs**: the button becomes
     "Open installer" and the user runs it manually.
4. Settings → About also offers:
   - **Check for updates** — manual check with inline status
     ("You're up to date" / opens the update dialog);
   - **What's new** — `ChangelogDialog` listing the full release history
     (version, date, notes) with the running version badged *installed*.

## API surface (`anisync/core/updater.py`)

| call | purpose |
|---|---|
| `latest()` | newest release or `None` |
| `check()` | newest release only if newer than `anisync.__version__` |
| `releases(limit=10)` | history, newest first; `[]` on any error |
| `check_with_news()` | `(latest, missed_releases)` or `None` |
| `download_asset(asset, dir, progress=cb)` | streamed download, `cb(done, total)` throttled |
| `compose_release_notes_md(releases, current_version=…)` | markdown digest for the dialogs |

## Configuration

| key                          | default              | meaning                                |
|------------------------------|----------------------|----------------------------------------|
| `update_repo`                | `DenisHumen/Anisync` | `owner/repo` on GitHub                 |
| `check_updates_on_start`     | `true`               | disable to skip the startup check      |

Stored in `<data_dir>/config.toml`; both editable in Settings.

## Asset naming

`ReleaseInfo.asset_for_platform()` matches case-insensitive suffixes:

| platform | suffix priority                                   |
|----------|---------------------------------------------------|
| macOS    | `.dmg`, `-mac.zip`, `-macos.zip`, `.pkg`          |
| Windows  | `-setup.exe`, `.msi`, `.exe`, `-win.zip`          |
| Linux    | `.AppImage`, `.deb`, `.rpm`, `-linux.tar.gz`      |

If nothing matches, the first asset is returned as a fallback.

## Offline behaviour

Any HTTP error (timeout, DNS failure, 404, rate limit) returns
`None`/`[]` — the app launches normally with no popup, the changelog
dialog shows a friendly offline message. The updater never blocks
startup.

## Tests

`tests/test_updater.py` covers version parsing, `is_newer`, per-platform
asset selection, `latest()`/`check()` via `httpx.MockTransport`,
release-history filtering (drafts/prereleases), `check_with_news`
missed-version aggregation, download progress + atomic `*.part` rename,
and the markdown digest (ordering, badges, empty bodies).
`tests/test_selfupdate.py` covers install-target detection per platform.
