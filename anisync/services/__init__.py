"""Cross-cutting application services.

This package is the home for **stateful service objects** that the rest
of the app talks to through small, well-typed facades:

* ``auth``    — sign-in / account management (re-exports
                :class:`anisync.core.auth.AuthService`)
* ``updater`` — GitHub release polling
                (re-exports :class:`anisync.core.updater.UpdateService`)
* ``library`` — local SQLite library / history
                (re-exports :func:`anisync.core.library.get_library`)
* ``downloads`` — concurrent download manager
                (re-exports :func:`anisync.core.downloader.get_manager`)

The implementations currently live under ``anisync.core.*`` for
historical reasons. New cross-cutting services should be added **here**
directly — keep ``anisync.core`` for pure data models, registries and
pluggable interfaces, and ``anisync.services`` for runtime state.

The re-exports below give callers a stable import surface so we can
move the implementations later without breaking the rest of the code.
"""
from anisync.core.auth import AuthService          # noqa: F401
from anisync.core.downloader import get_manager    # noqa: F401
from anisync.core.library import get_library       # noqa: F401
from anisync.core.updater import UpdateService     # noqa: F401

__all__ = ["AuthService", "UpdateService", "get_library", "get_manager"]
