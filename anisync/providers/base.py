"""Abstract base class every provider must implement."""
from __future__ import annotations

from abc import ABC, abstractmethod

from anisync.core.models import Anime, AnimeSummary, Episode


class BaseProvider(ABC):
    """Contract for an anime source. See ``docs/PROVIDERS.md``."""

    id: str = ""
    display_name: str = ""
    base_url: str = ""
    language: str = "ru"

    def __init_subclass__(cls, **kw):  # type: ignore[no-untyped-def]
        super().__init_subclass__(**kw)
        if cls.__module__.endswith(".base"):
            return
        if not getattr(cls, "id", None):
            raise TypeError(f"{cls.__name__}: 'id' must be set")
        if not getattr(cls, "display_name", None):
            raise TypeError(f"{cls.__name__}: 'display_name' must be set")

    @abstractmethod
    async def search(self, query: str, *, limit: int = 20) -> list[AnimeSummary]:
        """Return up to ``limit`` matches for ``query``."""

    @abstractmethod
    async def get_anime(self, anime_url: str) -> Anime:
        """Fetch full details. ``anime_url`` is either a canonical URL or slug."""

    @abstractmethod
    async def list_episodes(self, anime: Anime) -> list[Episode]:
        """Return all episodes for ``anime`` ordered by episode number."""

    # ─── helpers ──────────────────────────────────────────────────────────

    def __repr__(self) -> str:  # pragma: no cover - debug only
        return f"<Provider {self.id} ({self.display_name})>"
