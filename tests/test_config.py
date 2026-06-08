"""Config TOML round-trip — must survive Windows paths and corrupt files."""
from __future__ import annotations

import anisync.core.config as config_mod
from anisync.core.config import Config


def _redirect(tmp_path, monkeypatch):
    cfgfile = tmp_path / "config.toml"
    monkeypatch.setattr(config_mod, "config_path", lambda: cfgfile)
    return cfgfile


def test_roundtrip_with_windows_path(tmp_path, monkeypatch):
    cfgfile = _redirect(tmp_path, monkeypatch)
    cfg = Config(
        downloads_dir=r"C:\Users\Денис\Videos\Anisync",
        preferred_quality='1080p "hd"',  # embedded quotes too
    )
    cfg.save()
    # The on-disk file must be valid TOML (backslashes escaped).
    loaded = Config.load()
    assert loaded.downloads_dir == r"C:\Users\Денис\Videos\Anisync"
    assert loaded.preferred_quality == '1080p "hd"'
    assert cfgfile.exists()


def test_corrupt_config_resets_to_defaults(tmp_path, monkeypatch):
    cfgfile = _redirect(tmp_path, monkeypatch)
    # The exact shape that crashed on Windows: an unescaped backslash path.
    cfgfile.write_text('downloads_dir = "C:\\Users\\x"\n', "utf-8")
    cfg = Config.load()  # must NOT raise
    assert cfg.downloads_dir == Config().downloads_dir
    # …and it should have rewritten a valid file that now round-trips.
    assert Config.load().downloads_dir == Config().downloads_dir


def test_first_run_creates_valid_config(tmp_path, monkeypatch):
    _redirect(tmp_path, monkeypatch)
    first = Config.load()       # no file yet → defaults + save
    second = Config.load()      # reads the file it just wrote
    assert second.downloads_dir == first.downloads_dir
    assert second.update_repo == "DenisHumen/Anisync"
