"""Entry point: ``python -m anisync``."""
from __future__ import annotations

import sys


def main() -> int:
    # ``--selfcheck`` boots the plugin registries and reports them without
    # starting the GUI. Used to smoke-test a frozen build (verifies the
    # dynamically-imported providers/players actually made it into the bundle).
    if "--selfcheck" in sys.argv:
        import anisync
        from anisync.core.registry import (
            load_all,
            player_registry,
            provider_registry,
        )

        load_all()
        print(f"anisync {anisync.__version__}")
        # Exercise the config round-trip — this is what crashed on Windows
        # (unescaped backslash paths), so it must be part of the smoke test.
        from anisync.core.config import Config
        Config.load()
        print("config: OK")
        print("providers:", ", ".join(sorted(provider_registry)) or "(none)")
        print("players:", ", ".join(sorted(player_registry)) or "(none)")
        try:
            import ctypes.util

            from anisync.utils.mpv_loader import ensure_libmpv, load_mpv
            ensure_libmpv()
            resolved = ctypes.util.find_library("mpv")
            load_mpv()
            print(f"libmpv: OK -> {resolved}")
        except Exception as exc:  # noqa: BLE001
            print(f"libmpv: MISSING ({exc})")
        ok = bool(provider_registry) and bool(player_registry)
        print("selfcheck:", "OK" if ok else "FAILED")
        # libmpv is reported but not required for a passing selfcheck in dev;
        # CI can grep the "libmpv: OK" line to enforce it for releases.
        return 0 if ok else 1

    # Import lazily so ``python -m anisync --help`` style flags or pytest
    # collection do not pay PySide6's import cost.
    from anisync.app import run

    return run(sys.argv)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
