from __future__ import annotations

import httpx
import pytest

from anisync.providers.yummyanime import YummyAnimeProvider, _slug_from_url


@pytest.fixture
def mock_client(fixtures_dir):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        params = dict(request.url.params)
        if path == "/api/search":
            q = params.get("q", "")
            if not q:
                return httpx.Response(400, text="missing q")
            return httpx.Response(
                200, text=(fixtures_dir / "yummyanime" / "search_naruto.json").read_text("utf-8"),
                headers={"content-type": "application/json"},
            )
        if path == "/api/anime/vy-arestovany-1" or path == "/api/anime/9342":
            return httpx.Response(
                200, text=(fixtures_dir / "yummyanime" / "anime_9342.json").read_text("utf-8"),
                headers={"content-type": "application/json"},
            )
        if path.endswith("/videos"):
            return httpx.Response(
                200, text=(fixtures_dir / "yummyanime" / "videos_9342.json").read_text("utf-8"),
                headers={"content-type": "application/json"},
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(transport=transport, base_url="https://old.yummyani.me")


def test_slug_extraction():
    assert _slug_from_url("vy-arestovany-1") == "vy-arestovany-1"
    assert _slug_from_url("/catalog/item/vy-arestovany-1") == "vy-arestovany-1"
    assert (
        _slug_from_url("https://old.yummyani.me/catalog/item/vy-arestovany-1")
        == "vy-arestovany-1"
    )


async def test_search_parses_response(mock_client):
    provider = YummyAnimeProvider(client=mock_client)
    results = await provider.search("naruto", limit=5)
    assert results, "should return results"
    first = results[0]
    assert first.provider_id == "yummyanime"
    assert first.title
    assert first.url
    assert first.poster_url and first.poster_url.startswith("https://")
    await mock_client.aclose()


async def test_get_anime_full_metadata(mock_client):
    provider = YummyAnimeProvider(client=mock_client)
    anime = await provider.get_anime("vy-arestovany-1")
    assert anime.title == "Вы арестованы"
    assert anime.year == 1996
    assert "Комедия" in anime.genres
    assert anime.description.startswith("Работа дорожного")
    assert anime.poster_url and "static.yani.tv" in anime.poster_url
    assert anime.extra.get("anime_id") == 9342
    await mock_client.aclose()


async def test_list_episodes_returns_sorted_kodik_iframes(mock_client):
    provider = YummyAnimeProvider(client=mock_client)
    anime = await provider.get_anime("vy-arestovany-1")
    eps = await provider.list_episodes(anime)
    assert len(eps) > 10
    assert [e.number for e in eps] == sorted(e.number for e in eps)
    first = eps[0]
    assert first.number == 1
    assert first.embed_url.startswith("https://") and "kodikplayer.com" in first.embed_url
    assert first.dub  # AniDUB
    await mock_client.aclose()


async def test_search_empty_query_returns_no_request(mock_client):
    provider = YummyAnimeProvider(client=mock_client)
    assert await provider.search("   ") == []
    await mock_client.aclose()
