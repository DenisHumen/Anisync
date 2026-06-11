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
    compose_release_notes_md,
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


# ── release history / news ──────────────────────────────────────────────


def test_parse_release_published_at_and_prerelease():
    rel = _parse_release({
        "tag_name": "v1.0.0",
        "published_at": "2026-05-12T10:03:00Z",
        "prerelease": True,
    })
    assert rel.published_at is not None
    assert (rel.published_at.year, rel.published_at.month) == (2026, 5)
    assert rel.prerelease is True
    # malformed date must not raise
    assert _parse_release({"tag_name": "v1", "published_at": "garbage"}).published_at is None


async def test_releases_skips_drafts_and_prereleases(monkeypatch):
    payload = [
        {"tag_name": "v0.4.0", "draft": True},
        {"tag_name": "v0.3.0", "prerelease": True},
        {"tag_name": "v0.2.0", "published_at": "2026-02-01T00:00:00Z"},
        {"tag_name": "v0.1.0", "published_at": "2026-01-01T00:00:00Z"},
    ]
    _mock_client(monkeypatch, lambda req: httpx.Response(200, json=payload))
    rels = await UpdateService("u/r").releases()
    assert [r.tag for r in rels] == ["v0.2.0", "v0.1.0"]


async def test_releases_returns_empty_on_error(monkeypatch):
    _mock_client(monkeypatch, lambda req: httpx.Response(403, json={"message": "rate limit"}))
    assert await UpdateService("u/r").releases() == []


async def test_check_with_news_lists_missed_versions(monkeypatch):
    import anisync
    monkeypatch.setattr(anisync, "__version__", "0.1.0")
    payload = [
        {"tag_name": "v0.3.0"},
        {"tag_name": "v0.2.0"},
        {"tag_name": "v0.1.0"},
    ]
    _mock_client(monkeypatch, lambda req: httpx.Response(200, json=payload))
    result = await UpdateService("u/r").check_with_news()
    assert result is not None
    latest, news = result
    assert latest.version == "0.3.0"
    assert [r.version for r in news] == ["0.3.0", "0.2.0"]


async def test_check_with_news_none_when_up_to_date(monkeypatch):
    import anisync
    monkeypatch.setattr(anisync, "__version__", "9.9.9")
    payload = [{"tag_name": "v0.2.0"}, {"tag_name": "v0.1.0"}]
    _mock_client(monkeypatch, lambda req: httpx.Response(200, json=payload))
    assert await UpdateService("u/r").check_with_news() is None


# ── download with progress ──────────────────────────────────────────────


async def test_download_asset_reports_progress_and_is_atomic(tmp_path, monkeypatch):
    content = b"x" * (300 * 1024)
    _mock_client(monkeypatch, lambda req: httpx.Response(
        200, content=content, headers={"Content-Length": str(len(content))},
    ))
    calls: list[tuple[int, int]] = []
    out = await UpdateService("u/r").download_asset(
        ReleaseAsset(name="build.bin", url="https://x/build.bin", size=len(content)),
        tmp_path,
        progress=lambda done, total: calls.append((done, total)),
    )
    assert out == tmp_path / "build.bin"
    assert out.read_bytes() == content
    assert not (tmp_path / "build.bin.part").exists()   # renamed, no leftovers
    assert calls, "progress callback never invoked"
    assert calls[-1] == (len(content), len(content))    # final 100% report


# ── markdown digest for the dialogs ─────────────────────────────────────


def _rel(version: str, body: str = "") -> ReleaseInfo:
    return ReleaseInfo(version=version, tag=f"v{version}", html_url="", body=body, assets=())


def test_compose_release_notes_md_badges_and_order():
    md = compose_release_notes_md(
        [_rel("0.3.0", "- fast"), _rel("0.2.0", "- fix"), _rel("0.1.0")],
        current_version="0.2.0",
    )
    assert md.index("v0.3.0") < md.index("v0.2.0") < md.index("v0.1.0")
    assert "new" in md.split("v0.3.0", 1)[1].split("\n", 1)[0]
    assert "installed" in md.split("v0.2.0", 1)[1].split("\n", 1)[0]
    assert "_No release notes._" in md          # empty body placeholder
    assert "- fast" in md and "- fix" in md     # bodies preserved


def test_compose_release_notes_md_empty():
    assert "No releases" in compose_release_notes_md([])
