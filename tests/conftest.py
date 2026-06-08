"""Pytest config & fixtures."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

# Make sure the app uses a tmp data dir for tests
os.environ.setdefault("ANISYNC_TEST_MODE", "1")


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def load_json(fixtures_dir):
    def _load(rel: str):
        return json.loads((fixtures_dir / rel).read_text("utf-8"))
    return _load


@pytest.fixture
def tmp_library(tmp_path):
    from anisync.core.library import LibraryService
    db = tmp_path / "lib.db"
    svc = LibraryService(db)
    yield svc
    svc.close()
