# Player resolvers — turning embed URLs into streams

Anime sites rarely host video themselves; they embed a third-party player
(Kodik, Aniboom, Sibnet, VK, …). A **player resolver** takes the embed
URL and returns one or more `VideoSource` objects that the in-app player
and the downloader can consume.

## Contract

```python
# anisync/players/base.py
class BasePlayerResolver(ABC):
    id: str                                  # e.g. "kodik"
    domains: tuple[str, ...]                 # ("kodik.cc", "kodikapi.com")

    def can_resolve(self, embed_url: str) -> bool: ...
    async def resolve(self, embed_url: str) -> list[VideoSource]: ...
```

`VideoSource` carries `url`, `quality` ("720p"), `mime`, `headers`
(referer/UA the host requires) and optional `subtitles`.

## Registration

```python
from anisync.core.registry import register_player

@register_player
class MyResolver(BasePlayerResolver):
    id = "mysite-player"
    domains = ("mysite-player.com",)
    ...
```

Add `from . import mysite_player` in `anisync/players/__init__.py`.

## Strategy: use yt-dlp where possible

`yt-dlp` already supports Kodik and many other embed hosts. The default
implementation strategy is:

```python
async def resolve(self, embed_url: str) -> list[VideoSource]:
    info = await run_in_thread(yt_dlp_extract, embed_url)
    return [VideoSource(...) for f in info["formats"]]
```

This keeps each resolver small and benefits from yt-dlp's frequent
upstream fixes. Custom JS-decryption resolvers can be added later when a
host is not supported.

## Reference implementation — `kodik`

`anisync/players/kodik.py`:

- Matches `*.kodik.cc`, `*.kodik.info`, `aniqit.com`.
- Delegates extraction to yt-dlp (`KodikIE`).
- Returns one `VideoSource` per available resolution.
- Sets `Referer` header to `https://kodik.info/` (required by Kodik's CDN).
