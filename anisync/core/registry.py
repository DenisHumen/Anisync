"""Plugin registries for providers and player resolvers.

Plugins self-register at import time using the decorators below. The
:func:`load_all` helper is called once at app startup and triggers the
side-effect imports in :mod:`anisync.providers` and
:mod:`anisync.players`.
"""
from __future__ import annotations

import importlib
import pkgutil
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from anisync.players.base import BasePlayerResolver
    from anisync.providers.base import BaseProvider

P = TypeVar("P", bound="BaseProvider")
R = TypeVar("R", bound="BasePlayerResolver")


class _Registry(dict):
    """Tiny dict subclass that exposes a nicer ``register`` decorator."""

    def register(self, cls):  # type: ignore[no-untyped-def]
        instance = cls()
        if instance.id in self:
            raise ValueError(f"Duplicate plugin id: {instance.id!r}")
        self[instance.id] = instance
        return cls


provider_registry: _Registry = _Registry()
player_registry: _Registry = _Registry()


def register_provider(cls: type[P]) -> type[P]:
    """Class decorator: register a provider in :data:`provider_registry`."""
    provider_registry.register(cls)
    return cls


def register_player(cls: type[R]) -> type[R]:
    """Class decorator: register a player resolver in :data:`player_registry`."""
    player_registry.register(cls)
    return cls


def resolve_for(embed_url: str) -> "BasePlayerResolver | None":
    """Return the first player resolver that claims an embed URL."""
    for resolver in player_registry.values():
        if resolver.can_resolve(embed_url):
            return resolver
    return None


def _import_submodules(pkg_name: str) -> None:
    pkg = importlib.import_module(pkg_name)
    for mod in pkgutil.iter_modules(pkg.__path__):
        if mod.name.startswith("_") or mod.name == "base":
            continue
        importlib.import_module(f"{pkg_name}.{mod.name}")


def load_all() -> None:
    """Import every provider / player module so they self-register."""
    _import_submodules("anisync.providers")
    _import_submodules("anisync.players")
