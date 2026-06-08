"""Locate libmpv so ``import mpv`` works everywhere — including frozen builds.

In a packaged app the native libmpv (+ its ffmpeg/libass deps) is bundled by
PyInstaller next to the executable, so we must look *there first*. In a normal
dev checkout we fall back to the usual system locations (Homebrew on macOS is
not on the default dyld search path that ``ctypes.util.find_library`` uses).
"""
from __future__ import annotations

import ctypes.util
import os
import sys
from pathlib import Path

# System fallbacks (dev installs).
_SYSTEM_CANDIDATES = (
    "/opt/homebrew/lib/libmpv.dylib",
    "/opt/homebrew/lib/libmpv.2.dylib",
    "/usr/local/lib/libmpv.dylib",
    "/usr/local/lib/libmpv.2.dylib",
    "/usr/lib/libmpv.so.2",
    "/usr/lib/x86_64-linux-gnu/libmpv.so.2",
)

# Library file names per platform, searched inside the bundle.
_BUNDLED_NAMES = (
    "libmpv.dylib", "libmpv.2.dylib",          # macOS
    "libmpv-2.dll", "mpv-2.dll", "mpv-1.dll",  # Windows
    "libmpv.so.2", "libmpv.so",                # Linux
)

_patched = False


def _bundle_dirs() -> list[Path]:
    """Directories to scan for a bundled libmpv in a frozen app."""
    if not getattr(sys, "frozen", False):
        return []
    dirs: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        base = Path(meipass)
        dirs += [base, base / "lib", base.parent / "Frameworks"]
    exe_dir = Path(sys.executable).resolve().parent
    dirs += [exe_dir, exe_dir.parent / "Frameworks", exe_dir / "lib"]
    return dirs


def _find_bundled() -> str | None:
    for d in _bundle_dirs():
        for name in _BUNDLED_NAMES:
            p = d / name
            if p.exists():
                return str(p)
    return None


def ensure_libmpv() -> None:
    global _patched
    if _patched:
        return
    _orig = ctypes.util.find_library

    def _find(name: str):
        if name == "mpv":
            bundled = _find_bundled()
            if bundled:
                return bundled
            for p in _SYSTEM_CANDIDATES:
                if os.path.exists(p):
                    return p
        return _orig(name)

    ctypes.util.find_library = _find  # type: ignore[assignment]
    _patched = True


def load_mpv():
    """Import and return the ``mpv`` module, patching the loader first."""
    ensure_libmpv()
    import mpv  # noqa: WPS433
    return mpv
