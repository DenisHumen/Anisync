"""Player resolver base class. See ``docs/PLAYERS.md``."""
from __future__ import annotations

from abc import ABC, abstractmethod
from urllib.parse import urlparse

from anisync.core.models import VideoSource


class BasePlayerResolver(ABC):
    id: str = ""
    domains: tuple[str, ...] = ()

    def __init_subclass__(cls, **kw):  # type: ignore[no-untyped-def]
        super().__init_subclass__(**kw)
        if cls.__module__.endswith(".base"):
            return
        if not getattr(cls, "id", None):
            raise TypeError(f"{cls.__name__}: 'id' required")

    def can_resolve(self, embed_url: str) -> bool:
        try:
            host = urlparse(embed_url).hostname or ""
        except Exception:
            return False
        return any(host == d or host.endswith("." + d) for d in self.domains)

    @abstractmethod
    async def resolve(self, embed_url: str) -> list[VideoSource]:
        """Return playable streams sorted by quality (highest first)."""
