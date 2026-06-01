"""Locate libmpv on systems where ctypes.util.find_library cannot.

macOS Homebrew installs libmpv into /opt/homebrew/lib (Apple Silicon) or
/usr/local/lib (Intel) — neither is on the default dyld search path used
by ctypes.find_library. We patch find_library so `import mpv` succeeds.
"""
from __future__ import annotations

import ctypes.util
import os
import sys

_CANDIDATES = (
    "/opt/homebrew/lib/libmpv.dylib",
    "/opt/homebrew/lib/libmpv.2.dylib",
    "/usr/local/lib/libmpv.dylib",
    "/usr/local/lib/libmpv.2.dylib",
)

_patched = False


def ensure_libmpv() -> None:
    global _patched
    if _patched:
        return
    _orig = ctypes.util.find_library

    def _find(name: str):
        if name == "mpv":
            for p in _CANDIDATES:
                if os.path.exists(p):
                    return p
        return _orig(name)

    ctypes.util.find_library = _find  # type: ignore[assignment]
    _patched = True


def load_mpv():
    """Import and return the `mpv` module, patching the loader first."""
    ensure_libmpv()
    import mpv  # noqa: WPS433
    return mpv
