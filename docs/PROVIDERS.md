# Providers — adding a new anime source

A provider is a self-contained module under `anisync/providers/` that knows
how to **search**, **fetch metadata** and **list episodes** for one site.
Providers do **not** resolve playable streams — that is delegated to
[player resolvers](PLAYERS.md).

## Contract

```python
# anisync/providers/base.py
class BaseProvider(ABC):
    id: str                # unique slug, e.g. "yummyanime"
    display_name: str      # shown in UI, e.g. "YummyAnime"
    base_url: str          # e.g. "https://old.yummyani.me"
    language: str = "ru"   # ISO code of catalog language

    async def search(self, query: str, *, limit: int = 20) -> list[AnimeSummary]: ...
    async def get_anime(self, anime_url: str) -> Anime: ...
    async def list_episodes(self, anime: Anime) -> list[Episode]: ...
```

Return types live in `anisync.core.models`.

## Registration

Use the decorator:

```python
from anisync.core.registry import register_provider
from anisync.providers.base import BaseProvider

@register_provider
class MyProvider(BaseProvider):
    id = "mysite"
    display_name = "MySite"
    base_url = "https://example.com"
    ...
```

Then add the import to `anisync/providers/__init__.py`:

```python
from . import mysite  # noqa: F401
```

Done — the new provider appears everywhere: search dropdown, settings,
filter chips, etc.

## Implementation checklist

1. **HTTP client** — use `anisync.utils.http.get_client(provider_id)` so
   timeouts, retries and User-Agent are uniform.
2. **Parsing** — prefer `selectolax` (already a dep) over BeautifulSoup
   for speed; for embedded JSON use `json.loads`.
3. **Episodes** — fill `Episode.embed_url` with the raw embed (e.g. a
   `kodik.cc` iframe `src`). The player registry takes it from there.
4. **Errors** — raise `ProviderError` / `ProviderParseError` from
   `anisync.core.errors`.
5. **Tests** — store a sample HTML response in
   `tests/fixtures/<provider>/` and write a parse test using
   `httpx.MockTransport`. Network must never be touched in tests.

## Reference implementation — `yummyanime`

`anisync/providers/yummyanime.py` is the canonical example:

- `search()` scrapes `…/catalog/?search=…`.
- `get_anime()` parses `/catalog/item/<slug>` for title, poster,
  description, year, genres, episode count, dubs.
- `list_episodes()` extracts the JSON state blob embedded in the item
  page (Vue/Nuxt-style hydration) and yields one `Episode` per entry.
- Embed URLs are Kodik iframes resolved by
  `anisync.players.kodik.KodikResolver`.

If YummyAnime's HTML changes, only the parser inside that file should
need updating — UI/core are insulated.
