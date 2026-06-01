"""Kodik resolver — direct ``/ftor`` scraper.

yt-dlp removed its Kodik extractor in recent releases, so we implement
the scrape ourselves. The flow:

1. ``GET`` the embed page (``kodikplayer.com/video/...`` or
   ``.../season/...``) to harvest the signed ``urlParams`` JSON and the
   per-video ``vInfo`` ``{type, hash, id}`` triple.
2. ``POST`` the same parameters as raw ``application/x-www-form-urlencoded``
   to ``/ftor`` on the embed host. The server is *very* picky:
   - The body must not be percent-encoded (curl-style raw ``key=value``
     pairs). httpx's default form encoder breaks colons / braces and
     produces ``HTTP 500``.
   - ``info={}`` must be present.
3. Decode the obfuscated ``links[quality][0].src`` strings via the JS
   algorithm pulled live from ``app.player_single.<hash>.js``: each
   ASCII letter is shifted by +18 modulo the alphabet, then the result
   is base64-decoded.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
from urllib.parse import urlparse

import httpx

from anisync.core.errors import ResolveError
from anisync.core.models import VideoSource
from anisync.core.registry import register_player
from anisync.players.base import BasePlayerResolver

log = logging.getLogger(__name__)

_REFERER = "https://kodik.info/"
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_URL_PARAMS_RE = re.compile(r"var urlParams = '([^']+)'")
_VIDEO_ID_RE = re.compile(r'var videoId = "(\d+)"')
_HASH_RE = re.compile(r"vInfo\.hash = '([^']+)'")
_TYPE_RE = re.compile(r"vInfo\.type = '([^']+)'")


def _kodik_decode(s: str) -> str:
    """Mirror of the JS decoder shipped in ``app.player_single.*.js``.

    Each ASCII letter is shifted by +18 (wrapping at Z=90 / z=122), then
    the resulting string is base64-decoded.
    """
    out_chars: list[str] = []
    for c in s:
        oc = ord(c)
        if 0x41 <= oc <= 0x5A or 0x61 <= oc <= 0x7A:
            cap = 90 if oc <= 0x5A else 122
            n = oc + 18
            out_chars.append(chr(n if n <= cap else n - 26))
        else:
            out_chars.append(c)
    encoded = "".join(out_chars)
    encoded += "=" * ((-len(encoded)) % 4)
    return base64.b64decode(encoded).decode("utf-8")


def _resolve_sync(embed_url: str) -> list[VideoSource]:
    host = urlparse(embed_url).netloc
    embed_origin = f"https://{host}"
    with httpx.Client(
        follow_redirects=True,
        timeout=20.0,
        headers={"User-Agent": _UA},
    ) as client:
        page = client.get(embed_url, headers={"Referer": _REFERER}).text
        m_url = _URL_PARAMS_RE.search(page)
        m_vid = _VIDEO_ID_RE.search(page)
        m_hash = _HASH_RE.search(page)
        m_type = _TYPE_RE.search(page)
        if not (m_url and m_vid and m_hash and m_type):
            raise ResolveError(
                "Kodik embed page is missing expected video info "
                "(player layout may have changed)."
            )
        try:
            url_params = json.loads(m_url.group(1))
        except json.JSONDecodeError as e:
            raise ResolveError(f"Kodik: bad urlParams JSON: {e}") from e

        # Build the body with raw, unencoded values. The server rejects
        # standard urlencoding for these signed parameters.
        items: list[tuple[str, str]] = [
            *((str(k), str(v)) for k, v in url_params.items()),
            ("hash", m_hash.group(1)),
            ("id", m_vid.group(1)),
            ("type", m_type.group(1)),
            ("bad_user", "true"),
            ("cdn_is_working", "true"),
            ("info", "{}"),
        ]
        body = "&".join(f"{k}={v}" for k, v in items).encode("utf-8")
        resp = client.post(
            f"{embed_origin}/ftor",
            content=body,
            headers={
                "Referer": embed_url,
                "Origin": embed_origin,
                "Content-Type": "application/x-www-form-urlencoded",
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json, text/javascript, */*; q=0.01",
            },
        )

    if resp.status_code != 200:
        raise ResolveError(
            f"Kodik /ftor returned HTTP {resp.status_code} "
            "(video may be region-blocked or temporarily unavailable)."
        )
    try:
        payload = resp.json()
    except ValueError as e:
        raise ResolveError(f"Kodik /ftor returned non-JSON: {e}") from e

    links = payload.get("links") or {}
    if not links:
        raise ResolveError("Kodik returned no playable links.")

    sources: list[VideoSource] = []
    for quality, variants in links.items():
        if not isinstance(variants, list) or not variants:
            continue
        raw = variants[0].get("src") if isinstance(variants[0], dict) else None
        if not raw:
            continue
        try:
            url = _kodik_decode(raw)
        except Exception as e:  # noqa: BLE001
            log.warning("Kodik decode failed for %sp: %s", quality, e)
            continue
        is_hls = ".m3u8" in url
        sources.append(
            VideoSource(
                url=url,
                quality=f"{quality}p",
                mime="application/vnd.apple.mpegurl" if is_hls else "video/mp4",
                is_hls=is_hls,
                headers={"Referer": _REFERER},
            )
        )

    if not sources:
        raise ResolveError("Kodik returned no decodable sources.")
    sources.sort(key=lambda s: s.height, reverse=True)
    return sources


@register_player
class KodikResolver(BasePlayerResolver):
    id = "kodik"
    domains = ("kodik.cc", "kodik.info", "kodikplayer.com", "aniqit.com")

    async def resolve(self, embed_url: str) -> list[VideoSource]:
        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(None, _resolve_sync, embed_url)
        except ResolveError:
            raise
        except Exception as e:  # noqa: BLE001
            log.warning("Kodik extraction failed for %s: %s", embed_url, e)
            raise ResolveError(f"Kodik extraction failed: {e}") from e
