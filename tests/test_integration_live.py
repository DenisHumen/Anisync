"""Live integration tests — hit real network endpoints.

Run explicitly:  ``pytest -m live``

These are skipped by default (see pyproject ``addopts = "-ra -m 'not live'"``).
The goal is to prove end-to-end that the providers and resolvers work
against the actual upstream services, per user request:

> Проводи реальные тесты это запуск реального функционала, это будет тесты
"""
from __future__ import annotations

import pytest

from anisync.core.registry import load_all, provider_registry, player_registry

load_all()


pytestmark = [pytest.mark.live]


# ─── YummyAnime ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_yummyanime_search_live() -> None:
    p = provider_registry["yummyanime"]
    results = await p.search("naruto", limit=5)
    assert len(results) >= 1, "search returned no results"
    s = results[0]
    assert s.title.strip()
    assert s.url, "url (slug) is empty"
    assert s.provider_id == "yummyanime"


@pytest.mark.asyncio
async def test_yummyanime_get_anime_live() -> None:
    p = provider_registry["yummyanime"]
    results = await p.search("naruto", limit=5)
    assert results, "need at least one search hit to drill into"
    anime = await p.get_anime(results[0].url)
    assert anime.title.strip()
    assert anime.provider_id == "yummyanime"


@pytest.mark.asyncio
async def test_yummyanime_list_episodes_live() -> None:
    p = provider_registry["yummyanime"]
    results = await p.search("naruto", limit=5)
    anime = await p.get_anime(results[0].url)
    episodes = await p.list_episodes(anime)
    assert len(episodes) >= 1, "no episodes parsed"
    ep = episodes[0]
    assert ep.embed_url or ep.video_url
    assert ep.number >= 1


# ─── Kodik resolver ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_kodik_resolver_live() -> None:
    """Pull an episode from yummyanime that has a Kodik embed, then resolve."""
    if "kodik" not in player_registry:
        pytest.skip("kodik player not registered")
    p = provider_registry["yummyanime"]
    results = await p.search("naruto", limit=3)
    embed: str | None = None
    for s in results:
        anime = await p.get_anime(s.url)
        episodes = await p.list_episodes(anime)
        for ep in episodes:
            if ep.embed_url and "kodik" in ep.embed_url:
                embed = ep.embed_url
                break
        if embed:
            break
    if not embed:
        pytest.skip("no Kodik embed found in fixtures")

    sources = await player_registry["kodik"].resolve(embed)
    assert len(sources) >= 1
    assert sources[0].url.startswith("http")
