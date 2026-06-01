"""Shared `httpx.AsyncClient` factory."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

_DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "ru,en;q=0.8",
}


def make_client(
    *,
    base_url: str = "",
    headers: dict[str, str] | None = None,
    timeout: float = 20.0,
) -> httpx.AsyncClient:
    h = {**_DEFAULT_HEADERS, **(headers or {})}
    return httpx.AsyncClient(
        base_url=base_url,
        headers=h,
        timeout=timeout,
        follow_redirects=True,
        http2=False,
    )


@asynccontextmanager
async def client(**kwargs) -> AsyncIterator[httpx.AsyncClient]:
    c = make_client(**kwargs)
    try:
        yield c
    finally:
        await c.aclose()
