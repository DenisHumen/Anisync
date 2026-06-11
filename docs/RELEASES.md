# Release engineering

Anisync ships installers for **macOS**, **Windows** and **Linux** through
GitHub Releases. The full pipeline runs in
[`.github/workflows/release.yml`](../.github/workflows/release.yml).

## Cutting a release

1. Bump the version in **both** places:
   - `anisync/__init__.py` → `__version__ = "X.Y.Z"`
   - `pyproject.toml` → `version = "X.Y.Z"`
2. Write the release notes to `.github/releases/vX.Y.Z.md` — this exact
   markdown becomes the GitHub release body **and** the changelog users
   see in the in-app update dialog (see [UPDATER.md](UPDATER.md)).
3. Commit, tag and push:

```bash
git tag -a vX.Y.Z -m "Anisync X.Y.Z"
git push origin main vX.Y.Z
```

The tag push launches the workflow which:

1. Spins up three runners (`macos-latest`, `windows-latest`, `ubuntu-22.04`).
2. Installs the package, PyInstaller and a native **libmpv** per OS
   (brew / apt / mpv-winbuild) so playback works out of the box.
3. Builds via `pyinstaller packaging/Anisync.spec` (force-collects the
   dynamically-imported providers/players, bundles libmpv + logo + icons).
4. Smoke-tests every bundle (`Anisync --selfcheck` must report providers
   and libmpv OK).
5. Packages per-OS artifacts:
   - **macOS** → `Anisync-X.Y.Z-mac.dmg` via `hdiutil`
   - **Windows** → `Anisync-X.Y.Z-win.zip` (portable one-folder build)
   - **Linux** → `Anisync-X.Y.Z.AppImage` via `appimagetool`
6. Creates/updates the GitHub release with the body from
   `.github/releases/vX.Y.Z.md` (generic fallback if missing) and
   attaches the artifacts.

The in-app updater looks up the asset whose name ends in the
platform-appropriate suffix and — in packaged builds — installs it in
place via `core/selfupdate.py`.

## Local build (for testing)

```bash
pip install pyinstaller
pyinstaller --noconfirm packaging/Anisync.spec
open dist/Anisync.app           # macOS
./dist/Anisync/Anisync          # Linux / Windows
```

## Code signing

Currently unsigned — macOS users need right-click → Open on first launch,
Windows shows SmartScreen. Adding signing certificates is a follow-up:
store secrets `MACOS_CERT_P12`, `MACOS_CERT_PASSWORD`, `WIN_PFX`,
`WIN_PFX_PASSWORD` and extend the workflow with `codesign` / `signtool`
steps.
