from __future__ import annotations

from anisync.core.registry import (
    load_all,
    player_registry,
    provider_registry,
    resolve_for,
)


def test_registries_populate_on_load():
    load_all()
    assert "yummyanime" in provider_registry
    assert "kodik" in player_registry


def test_resolve_for_picks_correct_resolver():
    load_all()
    r = resolve_for("https://kodikplayer.com/season/123/abc/720p")
    assert r is not None and r.id == "kodik"
    r2 = resolve_for("https://example.com/")
    assert r2 is None
