from __future__ import annotations

from anisync.players.kodik import KodikResolver


def test_can_resolve_known_hosts():
    r = KodikResolver()
    assert r.can_resolve("https://kodikplayer.com/season/x/y/720p")
    assert r.can_resolve("https://kodik.cc/seria/x")
    assert r.can_resolve("https://kodik.info/x")
    assert r.can_resolve("https://aniqit.com/seria/x")


def test_can_resolve_rejects_unrelated_hosts():
    r = KodikResolver()
    assert not r.can_resolve("https://youtube.com/")
    assert not r.can_resolve("https://example.com/kodik")
    assert not r.can_resolve("not a url at all")
