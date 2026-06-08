# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Anisync.

Build:  pyinstaller --noconfirm packaging/Anisync.spec

Key points:
* Providers / players are imported dynamically via ``pkgutil.iter_modules``
  (see ``anisync.core.registry.load_all``), which PyInstaller's static
  analysis cannot see — so we force-collect both subpackages.
* The app logo is package data and must be carried into the bundle.
* ``python-mpv`` binds to the *system* libmpv at runtime; the app degrades
  gracefully when it is absent, so we don't hard-fail the build on it.
"""
import ctypes.util
import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


def _find_libmpv():
    """Locate the native libmpv to bundle. CI sets ANISYNC_LIBMPV; otherwise
    we probe the usual locations (Homebrew / apt / system)."""
    env = os.environ.get("ANISYNC_LIBMPV")
    if env and os.path.exists(env):
        return os.path.realpath(env)
    candidates = [
        "/opt/homebrew/lib/libmpv.dylib", "/opt/homebrew/lib/libmpv.2.dylib",
        "/usr/local/lib/libmpv.dylib", "/usr/local/lib/libmpv.2.dylib",
        "/usr/lib/libmpv.so.2", "/usr/lib/x86_64-linux-gnu/libmpv.so.2",
        "/lib/x86_64-linux-gnu/libmpv.so.2",
    ]
    for c in candidates:
        if os.path.exists(c):
            return os.path.realpath(c)
    found = ctypes.util.find_library("mpv")
    return os.path.realpath(found) if found and os.path.exists(found) else None

ROOT = Path(SPECPATH).parent          # SPECPATH = packaging/
PKG = "Anisync"

# version → Info.plist / installer naming
_ver = "0.0.0"
try:
    _init = (ROOT / "anisync" / "__init__.py").read_text("utf-8")
    import re
    m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', _init)
    if m:
        _ver = m.group(1)
except Exception:
    pass

if sys.platform == "darwin":
    ICON = str(ROOT / "packaging" / "anisync.icns")
elif sys.platform.startswith("win"):
    ICON = str(ROOT / "packaging" / "anisync.ico")
else:
    ICON = str(ROOT / "packaging" / "anisync.png")

hiddenimports = (
    collect_submodules("anisync.providers")
    + collect_submodules("anisync.players")
    + ["mpv"]
)

datas = [
    (str(ROOT / "anisync" / "ui" / "assets" / "logo.png"), "anisync/ui/assets"),
]

# Bundle native libmpv (+ its ffmpeg/libass deps, which PyInstaller follows)
# so playback works out of the box — no `brew install mpv` for end users.
binaries = []
_libmpv = _find_libmpv()
if _libmpv:
    binaries.append((_libmpv, "."))
    print(f"[Anisync.spec] bundling libmpv: {_libmpv}")
else:
    print("[Anisync.spec] WARNING: libmpv not found — playback disabled in this build")

a = Analysis(
    [str(ROOT / "anisync" / "__main__.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=PKG,
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon=ICON,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name=PKG,
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{PKG}.app",
        icon=ICON,
        bundle_identifier="io.anisync.app",
        version=_ver,
        info_plist={
            "CFBundleShortVersionString": _ver,
            "CFBundleVersion": _ver,
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
        },
    )
