"""YummyAnime provider — https://old.yummyani.me

Uses the site's JSON API discovered by inspection:

- ``GET /api/search?q=<query>``                    – fuzzy search
- ``GET /api/anime/<id_or_alias>``                  – full metadata
- ``GET /api/anime/<id_or_alias>/videos``           – episode list with
  ``iframe_url`` to ``kodikplayer.com``.

The site can return either ``9342`` (numeric id) or ``vy-arestovany-1``
(URL alias) — both are accepted by the API. We normalize internally by
storing the alias as ``Anime.url`` (it survives renumbering).
"""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import httpx

from anisync.core.errors import ProviderError, ProviderParseError
from anisync.core.models import Anime, AnimeSummary, Episode
from anisync.core.registry import register_provider
from anisync.providers.base import BaseProvider
from anisync.utils.http import make_client

log = logging.getLogger(__name__)


def _abs_poster(url: str | None) -> str | None:
    if not url:
        return None
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("http"):
        return url
    return "https://static.yani.tv" + url


def _slug_from_url(value: str) -> str:
    """Accepts ``vy-arestovany-1`` or ``/catalog/item/vy-arestovany-1`` or full URL."""
    if value.startswith(("http://", "https://")):
        path = urlparse(value).path
    else:
        path = value
    if "/catalog/item/" in path:
        path = path.split("/catalog/item/", 1)[1]
    return path.strip("/").split("/", 1)[0]


def _pick_poster(poster: dict[str, Any] | None) -> str | None:
    if not isinstance(poster, dict):
        return None
    for key in ("big", "medium", "huge", "fullsize", "small", "mega"):
        if poster.get(key):
            return _abs_poster(poster[key])
    return None


@register_provider
class YummyAnimeProvider(BaseProvider):
    id = "yummyanime"
    display_name = "YummyAnime"
    base_url = "https://old.yummyani.me"
    language = "ru"

    # Allow tests to inject a custom AsyncClient (e.g. respx mock transport).
    def __init__(self, *, client: httpx.AsyncClient | None = None) -> None:
        self._injected = client

    def _client(self) -> httpx.AsyncClient:
        return self._injected or make_client(
            base_url=self.base_url,
            headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
        )

    async def _get_json(self, path: str, **params: Any) -> Any:
        client = self._client()
        try:
            try:
                resp = await client.get(path, params=params)
            except httpx.HTTPError as e:
                raise ProviderError(f"YummyAnime request failed: {e}") from e
            if resp.status_code >= 400:
                raise ProviderError(
                    f"YummyAnime {path} -> HTTP {resp.status_code}"
                )
            try:
                return resp.json()
            except ValueError as e:
                raise ProviderParseError(f"Non-JSON response from {path}") from e
        finally:
            if self._injected is None:
                await client.aclose()

    # ─── public API ────────────────────────────────────────────────────────

    async def search(self, query: str, *, limit: int = 20) -> list[AnimeSummary]:
        if not query.strip():
            return []
        data = await self._get_json("/api/search", q=query)
        items = data.get("response") if isinstance(data, dict) else None
        if not isinstance(items, list):
            raise ProviderParseError("search: missing 'response' list")
        out: list[AnimeSummary] = []
        for raw in items[:limit]:
            try:
                out.append(self._parse_summary(raw))
            except Exception as e:  # noqa: BLE001
                log.warning("Skipping malformed search hit: %s", e)
        return out

    async def get_anime(self, anime_url: str) -> Anime:
        slug = _slug_from_url(anime_url)
        data = await self._get_json(f"/api/anime/{slug}")
        resp = data.get("response") if isinstance(data, dict) else None
        if not isinstance(resp, dict):
            raise ProviderParseError("get_anime: missing 'response' object")
        return self._parse_anime(resp, slug)

    async def list_episodes(self, anime: Anime) -> list[Episode]:
        # The /videos endpoint requires the numeric anime_id; the slug
        # endpoint returns HTTP 400 for /videos. We resolve the id from
        # get_anime() (cached in ``anime.extra``) and only fall back to a
        # second metadata request if it is missing.
        anime_id = anime.extra.get("anime_id") if anime.extra else None
        if not anime_id:
            full = await self.get_anime(anime.url)
            anime_id = full.extra.get("anime_id")
        if not anime_id:
            raise ProviderParseError("list_episodes: missing anime_id")
        data = await self._get_json(f"/api/anime/{anime_id}/videos")
        resp = data.get("response") if isinstance(data, dict) else None
        if not isinstance(resp, list):
            raise ProviderParseError("list_episodes: missing 'response' list")
        out: list[Episode] = []
        for raw in resp:
            ep = self._parse_episode(raw, anime.url)
            if ep is not None:
                out.append(ep)
        out.sort(key=lambda e: e.number)
        return out

    # ─── parsers ──────────────────────────────────────────────────────────

    def _parse_summary(self, raw: dict[str, Any]) -> AnimeSummary:
        if not isinstance(raw, dict) or "anime_url" not in raw:
            raise ProviderParseError("search item missing 'anime_url'")
        return AnimeSummary(
            provider_id=self.id,
            url=str(raw["anime_url"]),
            title=str(raw.get("title") or raw.get("anime_url")),
            poster_url=_pick_poster(raw.get("poster")),
            year=raw.get("year"),
            type=(raw.get("type") or {}).get("name") if isinstance(raw.get("type"), dict) else None,
        )

    def _parse_anime(self, raw: dict[str, Any], slug_fallback: str) -> Anime:
        genres = tuple(
            str(g.get("title")) for g in raw.get("genres") or []
            if isinstance(g, dict) and g.get("title")
        )
        type_obj = raw.get("type")
        type_name = type_obj.get("name") if isinstance(type_obj, dict) else None
        status_obj = raw.get("anime_status")
        status_name = status_obj.get("title") if isinstance(status_obj, dict) else None
        rating_obj = raw.get("rating") or {}
        rating = rating_obj.get("average") if isinstance(rating_obj, dict) else None
        studios = tuple(
            str(s.get("title")) for s in raw.get("studios") or []
            if isinstance(s, dict) and s.get("title")
        )
        return Anime(
            provider_id=self.id,
            url=str(raw.get("anime_url") or slug_fallback),
            title=str(raw.get("title") or slug_fallback),
            original_title=raw.get("other_titles", {}).get("ru") if isinstance(raw.get("other_titles"), dict) else None,
            poster_url=_pick_poster(raw.get("poster")),
            description=str(raw.get("description") or "").strip(),
            year=raw.get("year"),
            type=type_name,
            status=status_name,
            genres=genres,
            studios=studios,
            episodes_count=raw.get("count_videos") or raw.get("series") or None,
            rating=float(rating) if isinstance(rating, (int, float)) else None,
            extra={"anime_id": raw.get("anime_id")},
        )

    def _parse_episode(self, raw: dict[str, Any], anime_url: str) -> Episode | None:
        if not isinstance(raw, dict):
            return None
        iframe = raw.get("iframe_url")
        if not iframe:
            return None
        if iframe.startswith("//"):
            iframe = "https:" + iframe
        try:
            number = int(raw.get("number") or raw.get("index") or 0)
        except (TypeError, ValueError):
            return None
        info = raw.get("data") or {}
        return Episode(
            provider_id=self.id,
            anime_url=anime_url,
            number=number,
            title=raw.get("title"),
            embed_url=iframe,
            dub=info.get("dubbing") if isinstance(info, dict) else None,
            player_name=info.get("player") if isinstance(info, dict) else None,
            duration=raw.get("duration"),
        )
