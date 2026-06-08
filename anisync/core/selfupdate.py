"""Self-update: replace the running app with a freshly-downloaded build.

Flow (driven by the UI):

1. :func:`can_self_update` — is this a frozen build we can replace in place?
2. download the platform asset (see :mod:`anisync.core.updater`).
3. :func:`stage` — unpack the asset into a staging dir (mount ``.dmg`` /
   unzip / copy ``.AppImage``) and return the new artifact.
4. :func:`apply_and_relaunch` — write a tiny detached helper that waits for
   *this* process to exit, swaps the new build over the old one, and relaunches.
   Then the caller quits the app.

The helper pattern is required because a process cannot replace its own
running executable/bundle on disk while it is open.
"""
from __future__ import annotations

import logging
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def installed_target() -> Path | None:
    """The path self-update replaces, or ``None`` if unsupported.

    * macOS  → the ``.app`` bundle
    * Windows → the one-folder install directory
    * Linux  → the running ``.AppImage`` (via ``$APPIMAGE``)
    """
    if not is_frozen():
        return None
    exe = Path(sys.executable).resolve()
    if sys.platform == "darwin":
        for parent in exe.parents:
            if parent.suffix == ".app":
                return parent
        return None
    if sys.platform.startswith("win"):
        return exe.parent
    appimage = os.environ.get("APPIMAGE")
    return Path(appimage) if appimage else None


def can_self_update() -> bool:
    target = installed_target()
    if target is None:
        return False
    # We need write access to the thing we are going to overwrite.
    probe = target if sys.platform.startswith("win") else target.parent
    return os.access(probe, os.W_OK)


def _staging_dir() -> Path:
    d = Path(tempfile.gettempdir()) / "anisync-update"
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True, exist_ok=True)
    return d


def stage(asset_path: Path) -> Path:
    """Unpack a downloaded asset and return the new build artifact.

    Blocking (mounts/unzips) — run it off the UI thread.
    """
    work = _staging_dir()
    name = asset_path.name.lower()

    if sys.platform == "darwin":
        if name.endswith(".dmg"):
            return _extract_app_from_dmg(asset_path, work)
        shutil.unpack_archive(str(asset_path), str(work))
        return _first(work, "*.app")

    if sys.platform.startswith("win"):
        # Asset is a zip of the one-folder build (possibly named .exe).
        target = work / "Anisync"
        shutil.unpack_archive(str(asset_path), str(target), format="zip")
        # zip may contain an extra top-level "Anisync" dir → flatten.
        inner = target / "Anisync"
        return inner if inner.is_dir() else target

    # Linux: the asset is the new AppImage itself.
    dest = work / asset_path.name
    shutil.copy2(asset_path, dest)
    dest.chmod(dest.stat().st_mode | stat.S_IEXEC)
    return dest


def _extract_app_from_dmg(dmg: Path, work: Path) -> Path:
    out = subprocess.run(
        ["hdiutil", "attach", "-nobrowse", "-readonly", str(dmg)],
        capture_output=True, text=True, check=True,
    )
    mount = None
    for line in out.stdout.splitlines():
        cols = line.split("\t")
        last = cols[-1].strip() if cols else ""
        if last.startswith("/Volumes/"):
            mount = last
    if not mount:
        raise RuntimeError("could not find DMG mount point")
    try:
        app = _first(Path(mount), "*.app")
        dest = work / app.name
        subprocess.run(["ditto", str(app), str(dest)], check=True)
        return dest
    finally:
        subprocess.run(["hdiutil", "detach", mount], capture_output=True)


def _first(root: Path, pattern: str) -> Path:
    for p in root.rglob(pattern):
        return p
    raise FileNotFoundError(f"no {pattern} inside {root}")


def apply_and_relaunch(new_artifact: Path) -> None:
    """Spawn a detached helper that swaps in ``new_artifact`` after we exit,
    then relaunches. The caller must quit the app right after."""
    target = installed_target()
    if target is None:
        raise RuntimeError("self-update is only supported in packaged builds")
    pid = os.getpid()
    if sys.platform == "darwin":
        script = _write_script(_MAC_SWAP)
        _spawn(["/bin/bash", script, str(pid), str(target), str(new_artifact)])
    elif sys.platform.startswith("win"):
        script = _write_script(_WIN_SWAP, suffix=".bat")
        exe = Path(sys.executable).name
        _spawn(["cmd", "/c", script, str(pid), str(target), str(new_artifact), exe])
    else:
        script = _write_script(_LINUX_SWAP)
        _spawn(["/bin/bash", script, str(pid), str(target), str(new_artifact)])


def _write_script(body: str, *, suffix: str = ".sh") -> str:
    fd, path = tempfile.mkstemp(prefix="anisync-swap-", suffix=suffix)
    with os.fdopen(fd, "w") as f:
        f.write(body)
    os.chmod(path, 0o755)
    return path


def _spawn(cmd: list[str]) -> None:
    log.info("Spawning update helper: %s", cmd)
    kwargs: dict = {}
    if sys.platform.startswith("win"):
        kwargs["creationflags"] = 0x00000008 | 0x00000200  # DETACHED | NEW_GROUP
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        **kwargs,
    )


_MAC_SWAP = r"""#!/bin/bash
PID="$1"; OLD="$2"; NEW="$3"
for _ in $(seq 1 150); do kill -0 "$PID" 2>/dev/null || break; sleep 0.2; done
sleep 0.5
/bin/rm -rf "$OLD"
/usr/bin/ditto "$NEW" "$OLD" || exit 1
/usr/bin/xattr -cr "$OLD" 2>/dev/null
/usr/bin/codesign --force --deep --sign - "$OLD" 2>/dev/null
/usr/bin/open "$OLD"
"""

_WIN_SWAP = r"""@echo off
set PID=%1
set OLD=%2
set NEW=%3
set EXE=%4
:wait
tasklist /FI "PID eq %PID%" 2>NUL | find "%PID%" >NUL
if not errorlevel 1 ( timeout /t 1 /nobreak >NUL & goto wait )
timeout /t 1 /nobreak >NUL
robocopy "%NEW%" "%OLD%" /MIR /NFL /NDL /NJH /NJS /NC /NS /NP >NUL
start "" "%OLD%\%EXE%"
"""

_LINUX_SWAP = r"""#!/bin/bash
PID="$1"; OLD="$2"; NEW="$3"
for _ in $(seq 1 150); do kill -0 "$PID" 2>/dev/null || break; sleep 0.2; done
sleep 0.3
/bin/mv -f "$NEW" "$OLD" || exit 1
/bin/chmod +x "$OLD"
"$OLD" >/dev/null 2>&1 &
"""
