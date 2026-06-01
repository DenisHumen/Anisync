# Release engineering

Anisync ships installers for **macOS**, **Windows** and **Linux** through
GitHub Releases. The full pipeline runs in [`.github/workflows/release.yml`](../.github/workflows/release.yml).

## Triggering a release

Push a tag matching `v*`:

```bash
git tag v0.2.0
git push origin v0.2.0
```

This launches the workflow which:

1. Spins up three runners (`macos-latest`, `windows-latest`, `ubuntu-latest`).
2. Installs the package + PyInstaller.
3. Runs `pyinstaller --windowed --name Anisync anisync/__main__.py`.
4. Packages per-OS installers:
   - **macOS** → `Anisync-X.Y.Z-mac.dmg` via `hdiutil`.
   - **Windows** → `Anisync-X.Y.Z-win-setup.exe` (initial zipped bundle; swap in Inno Setup or MSIX when desired).
   - **Linux** → `Anisync-X.Y.Z.AppImage` via `appimagetool`.
5. Uploads them as assets to the release that matches the pushed tag.

The in-app updater (see [UPDATER.md](UPDATER.md)) looks up the asset whose
name ends in the platform-appropriate suffix.

## Local build (for testing)

```bash
pip install pyinstaller
pyinstaller --noconfirm --windowed --name Anisync anisync/__main__.py
open dist/Anisync.app          # macOS
./dist/Anisync/Anisync          # Linux / Windows
```

## Code signing

Currently unsigned — macOS users will need to right-click → Open the first
time, Windows will show SmartScreen. Adding signing certificates is left
as a follow-up: store secrets `MACOS_CERT_P12`, `MACOS_CERT_PASSWORD`,
`WIN_PFX`, `WIN_PFX_PASSWORD` and extend the workflow with `codesign` /
`signtool` steps.
