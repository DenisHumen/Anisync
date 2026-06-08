#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# Anisync — one-shot dev launcher.
#
# 1. Bootstraps a local .venv (creates + installs deps on first run).
# 2. Verifies PySide6 can actually instantiate QApplication. A common
#    failure mode is a half-extracted PySide6 wheel where Qt's
#    factoryloader silently refuses every platform plugin even though
#    the .dylib exists on disk. In that case we auto-heal by
#    force-reinstalling the PySide6 stack.
# 3. Sets QT_QPA_PLATFORM_PLUGIN_PATH explicitly so the GUI starts
#    regardless of which shell/terminal is used.
#
# Temporary helper — final story is PyInstaller via GitHub Actions.
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

VENV="$ROOT/.venv"
# The real venv lives OUTSIDE the project tree. If the repo sits in a
# cloud-synced folder (iCloud Desktop&Documents, Dropbox, Google Drive),
# those services virtualize ("dataless") and conflict-copy the Qt binaries,
# which makes the platform plugin silently "vanish". Keeping the venv in the
# home dir avoids that entirely; ``.venv`` is just a symlink so activate /
# pip shebangs keep working.
VENV_REAL="${ANISYNC_VENV:-$HOME/.anisync-venv}"
PY="$VENV/bin/python"

# ── bootstrap venv ───────────────────────────────────────────────────────────
if [[ ! -x "$PY" ]]; then
  echo "[run.sh] Creating virtualenv at $VENV_REAL (outside the synced tree)"
  python3 -m venv "$VENV_REAL"
  ln -snf "$VENV_REAL" "$VENV"
  "$PY" -m pip install --upgrade pip wheel >/dev/null
  if [[ -f "$ROOT/requirements.txt" ]]; then
    "$PY" -m pip install -r "$ROOT/requirements.txt"
  fi
  "$PY" -m pip install -e "$ROOT"
fi

set_plugin_path() {
  PLUGIN_PATH="$("$PY" -c 'import os, PySide6; print(os.path.join(os.path.dirname(PySide6.__file__), "Qt", "plugins", "platforms"))')"
  export QT_QPA_PLATFORM_PLUGIN_PATH="$PLUGIN_PATH"
}

set_plugin_path
export QT_LOGGING_RULES="qt.qpa.fonts.warning=false"

# ── self-heal a broken PySide6 install ───────────────────────────────────────
if ! "$PY" -c "from PySide6.QtWidgets import QApplication; QApplication([])" >/dev/null 2>&1; then
  echo "[run.sh] PySide6 cannot start — force-reinstalling once…"
  "$PY" -m pip install --force-reinstall --no-deps \
    PySide6 PySide6_Essentials PySide6_Addons shiboken6
  set_plugin_path
fi

# ── run ──────────────────────────────────────────────────────────────────────
exec "$PY" -m anisync "$@"
