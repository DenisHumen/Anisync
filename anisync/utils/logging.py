"""Logging configured once for the whole app."""
from __future__ import annotations

import logging
import sys

_FMT = "%(asctime)s  %(levelname)-7s  %(name)s :: %(message)s"


def setup(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    if root.handlers:
        return
    h = logging.StreamHandler(sys.stderr)
    h.setFormatter(logging.Formatter(_FMT, datefmt="%H:%M:%S"))
    root.addHandler(h)
    root.setLevel(level)
    # noisy 3rd parties
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
