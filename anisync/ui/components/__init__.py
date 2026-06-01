"""Reusable UI **components** (atoms and molecules).

Drop in this package any presentational, side-effect-free widget that
could be reused across multiple pages (cards, carousels, empty-states,
chips, etc.). Keep page-specific widgets in :mod:`anisync.ui.widgets`.

For backwards compatibility, the existing primitives are re-exported
here so call sites can be migrated gradually:

    from anisync.ui.components import PosterCard, Carousel
"""
from anisync.ui.widgets.anime_card import PosterCard, AnimeCard   # noqa: F401
from anisync.ui.widgets.carousel import Carousel                  # noqa: F401

__all__ = ["PosterCard", "AnimeCard", "Carousel"]
