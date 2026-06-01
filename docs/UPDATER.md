# Updater

Anisync polls **GitHub Releases** at startup (unless disabled in
`Config.check_updates_on_start`) and offers to download the matching
installer if a newer version is available.

## Flow

1. `MainWindow.__init__` calls `UpdateService(cfg.update_repo).check()` via
   `run_async(...)`.
2. `UpdateService.check()` GETs `https://api.github.com/repos/{repo}/releases/latest`.
3. Tag is parsed (`v0.2.0` → `(0, 2, 0)`) and compared to
   `anisync.__version__`. Only newer versions return a `ReleaseInfo`.
4. `MainWindow._on_update_check` opens `UpdateDialog` which shows the
   changelog (`release.body`) and a "Download installer" button.
5. The dialog calls `UpdateService.download_asset(asset, dest_dir)` which
   streams the asset to `<data_dir>/updates/`. After the file is saved
   the button switches to "Open installer" — the user runs the
   installer manually (safer than auto-elevating).

## Configuration

| key                          | default            | meaning                                |
|------------------------------|--------------------|----------------------------------------|
| `update_repo`                | `anisync/anisync`  | `owner/repo` on GitHub                 |
| `check_updates_on_start`     | `true`             | disable to skip the check entirely     |

Stored in `<data_dir>/config.toml`.

## Asset naming

`ReleaseInfo.asset_for_platform()` matches case-insensitive suffixes:

| platform | suffix priority                                   |
|----------|---------------------------------------------------|
| macOS    | `.dmg`, `-mac.zip`, `-macos.zip`, `.pkg`          |
| Windows  | `-setup.exe`, `.msi`, `.exe`, `-win.zip`          |
| Linux    | `.AppImage`, `.deb`, `.rpm`, `-linux.tar.gz`      |

If nothing matches, the first asset is returned as a fallback.

## Offline behaviour

Any HTTP error (timeout, DNS failure, 404) returns `None` — the app
launches normally with no popup. The updater never blocks startup.

## Tests

`tests/test_updater.py` covers:

* version parsing (incl. malformed),
* `is_newer` comparisons,
* per-platform asset selection,
* `httpx.MockTransport` for `latest()` / `check()` (404 → None,
  same version → None, newer → release).
