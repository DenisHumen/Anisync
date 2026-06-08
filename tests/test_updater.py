"""Unit tests for the GitHub updater."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from anisync.core.updater import (
    ReleaseAsset,
    ReleaseInfo,
    UpdateService,
    _parse_release,
    is_newer,
    parse_version,
)


def test_parse_version_basic():
    assert parse_version("1.2.3") == (1, 2, 3)
    assert parse_version("v0.1") == (0, 1, 0)
    assert parse_version("2") == (2, 0, 0)
    assert parse_version("v1.4.0-rc1") == (1, 4, 0)
    assert parse_version("") == (0, 0, 0)
    assert parse_version("garbage") == (0, 0, 0)


def test_is_newer():
    assert is_newer("0.2.0", local="0.1.0") is True
    assert is_newer("0.1.0", local="0.1.0") is False
    assert is_newer("0.0.9", local="0.1.0") is False
    assert is_newer("1.0.0", local="0.9.9") is True


@pytest.mark.parametrize(
    "platform,assets,expected",
    [
        ("darwin", ["Anisync-1.0.0-mac.dmg", "Anisync-1.0.0-win-setup.exe"], "Anisync-1.0.0-mac.dmg"),
        ("win32", ["Anisync-1.0.0-mac.dmg", "Anisync-1.0.0-win-setup.exe"], "Anisync-1.0.0-win-setup.exe"),
        ("linux", ["Anisync-1.0.0-mac.dmg", "Anisync-1.0.0.AppImage"], "Anisync-1.0.0.AppImage"),
    ],
)
def test_asset_for_platform(platform, assets, expected, monkeypatch):
    rel = ReleaseInfo(
        version="1.0.0", tag="v1.0.0", html_url="", body="",
        assets=tuple(ReleaseAsset(name=n, url="https://x/" + n, size=1) for n in assets),
    )
    import sys as real_sys
    monkeypatch.setattr(real_sys, "platform", platform, raising=True)
    a = rel.asset_for_platform()
    assert a is not None, f"no asset for {platform}"
    assert a.name == expected


def test_asset_for_platform_falls_back_to_first():
    rel = ReleaseInfo(
        version="1.0.0", tag="v1.0.0", html_url="", body="",
        assets=(ReleaseAsset(name="weird.tar.bz2", url="x", size=1),),
    )
    a = rel.asset_for_platform()
    assert a is not None
    assert a.name == "weird.tar.bz2"


def test_parse_release_payload():
    rel = _parse_release({
        "tag_name": "v0.5.0",
        "html_url": "https://github.com/u/r/releases/tag/v0.5.0",
        "body": "## Changes\n- thing",
        "assets": [
            {"name": "Anisync-0.5.0-mac.dmg", "browser_download_url": "https://x/mac", "size": 12345},
            {"name": "noinfo", "browser_download_url": ""},  # filtered
        ],
    })
    assert rel.version == "0.5.0"
    assert rel.tag == "v0.5.0"
    assert "Changes" in rel.body
    assert len(rel.assets) == 1
    assert rel.assets[0].size == 12345


def _mock_client(monkeypatch, handler):
    """Replace httpx.AsyncClient inside the updater module so each call
    returns a client wired to a MockTransport."""
    real_cls = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs.pop("transport", None)
        return real_cls(*args, transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr("anisync.core.updater.httpx.AsyncClient", factory)


async def test_latest_returns_none_on_404(monkeypatch):
    _mock_client(monkeypatch, lambda req: httpx.Response(404, json={"message": "Not Found"}))
    svc = UpdateService("nobody/nothing")
    assert await svc.latest() is None


async def test_check_returns_none_when_same_version(monkeypatch):
    import anisync
    monkeypatch.setattr(anisync, "__version__", "9.9.9")
    _mock_client(monkeypatch, lambda req: httpx.Response(200, json={
        "tag_name": "v0.0.1", "html_url": "", "body": "", "assets": []
    }))
    svc = UpdateService("u/r")
    assert await svc.check() is None


async def test_check_returns_release_when_newer(monkeypatch):
    import anisync
    monkeypatch.setattr(anisync, "__version__", "0.0.1")
    _mock_client(monkeypatch, lambda req: httpx.Response(200, json={
        "tag_name": "v9.9.9", "html_url": "u", "body": "notes",
        "assets": [{"name": "x.dmg", "browser_download_url": "https://x/x.dmg", "size": 1}],
    }))
    svc = UpdateService("u/r")
    result = await svc.check()
    assert result is not None
    assert result.version == "9.9.9"
