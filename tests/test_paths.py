from __future__ import annotations

import anisync.utils.paths as paths
from anisync.utils.paths import safe_filename


def test_data_dir_respects_explicit_override(tmp_path, monkeypatch):
    target = tmp_path / "custom"
    monkeypatch.setenv("ANISYNC_DATA_DIR", str(target))
    assert paths.data_dir() == target
    assert target.is_dir()
    assert paths.config_path() == target / "config.toml"
    assert paths.library_db_path() == target / "library.db"


def test_data_dir_test_mode_avoids_real_user_dir(monkeypatch):
    monkeypatch.delenv("ANISYNC_DATA_DIR", raising=False)
    monkeypatch.setenv("ANISYNC_TEST_MODE", "1")
    d = paths.data_dir()
    assert "anisync-test" in str(d).lower()
    assert d.is_dir()


def test_safe_filename_removes_invalid_chars():
    assert safe_filename("a/b\\c:d*?") == "a b c d"
    # Trailing dots are stripped (Windows-hostile); leading dots are kept.
    assert safe_filename("hidden..") == "hidden"
    assert safe_filename("") == "untitled"
    assert safe_filename("   spaces   ") == "spaces"
    long = "x" * 500
    assert len(safe_filename(long)) <= 180
