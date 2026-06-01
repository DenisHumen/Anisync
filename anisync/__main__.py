"""Entry point: ``python -m anisync``."""
from __future__ import annotations

import sys


def main() -> int:
    # Import lazily so ``python -m anisync --help`` style flags or pytest
    # collection do not pay PySide6's import cost.
    from anisync.app import run

    return run(sys.argv)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
