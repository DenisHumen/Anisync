"""Site-specific scrapers. Each module self-registers via decorators."""
from __future__ import annotations

# Side-effect imports: each module calls @register_provider on import.
from . import yummyanime  # noqa: F401
