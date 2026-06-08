"""In-app updater backed by GitHub Releases.

Checks ``https://api.github.com/repos/<owner>/<repo>/releases/latest``
and compares the tag (``v0.2.0``) to the running :data:`anisync.__version__`.

When a newer release is found the UI offers to download the installer
matching the user's platform from the release assets:

* ``Anisync-<ver>-mac.dmg``        macOS
* ``Anisync-<ver>-win-setup.exe``  Windows
* ``Anisync-<ver>-linux.AppImage`` Linux

The downloaded installer is placed in the user's Downloads folder; we do
**not** auto-execute it — the user is shown a button to open the file
manually. This is the safe default that works on every OS without
admin/sudo.
"""
from __future__ import annotations

import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import httpx

import anisync

log = logging.getLogger(__name__)

GITHUB_REPO = "DenisHumen/Anisync"  # override via Config.update_repo


@dataclass(frozen=True)
class ReleaseAsset:
    name: str
    url: str
    size: int


@dataclass(frozen=True)
class ReleaseInfo:
    version: str            # e.g. "0.2.0"
    tag: str                # e.g. "v0.2.0"
    html_url: str
    body: str
    assets: tuple[ReleaseAsset, ...]

    def asset_for_platform(self) -> ReleaseAsset | None:
        plat = sys.platform
        candidates: Iterable[str]
        if plat == "darwin":
            candidates = (".dmg", "-mac.zip", "-macos.zip", ".pkg")
        elif plat.startswith("win"):
            candidates = ("-setup.exe", ".msi", ".exe", "-win.zip")
        else:
            candidates = (".AppImage", ".deb", ".rpm", "-linux.tar.gz")
        for suffix in candidates:
            s = suffix.lower()
            for a in self.assets:
                if a.name.lower().endswith(s):
                    return a
        return self.assets[0] if self.assets else None


# ── semver-ish comparison ────────────────────────────────────────────────


_VER_RX = re.compile(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?")


def parse_version(v: str) -> tuple[int, int, int]:
    """Best-effort numeric tuple. Non-numeric suffixes (``-rc1``) are ignored."""
    m = _VER_RX.search(v or "")
    if not m:
        return (0, 0, 0)
    return (int(m.group(1) or 0), int(m.group(2) or 0), int(m.group(3) or 0))


def is_newer(remote: str, local: str = anisync.__version__) -> bool:
    return parse_version(remote) > parse_version(local)


# ── service ──────────────────────────────────────────────────────────────


class UpdateService:
    def __init__(self, repo: str = GITHUB_REPO) -> None:
        self._repo = repo

    async def latest(self) -> ReleaseInfo | None:
        url = f"https://api.github.com/repos/{self._repo}/releases/latest"
        try:
            async with httpx.AsyncClient(timeout=10, headers={"Accept": "application/vnd.github+json"}) as c:
                r = await c.get(url)
        except httpx.HTTPError as e:
            log.info("Updater offline: %s", e)
            return None
        if r.status_code == 404:
            log.info("Updater: no releases published yet")
            return None
        if r.status_code >= 400:
            log.warning("Updater HTTP %s", r.status_code)
            return None
        return _parse_release(r.json())

    async def check(self) -> ReleaseInfo | None:
        """Return latest release **only if newer** than current version."""
        rel = await self.latest()
        if rel and is_newer(rel.version):
            return rel
        return None

    async def download_asset(self, asset: ReleaseAsset, dest_dir: Path) -> Path:
        dest_dir.mkdir(parents=True, exist_ok=True)
        out = dest_dir / asset.name
        async with httpx.AsyncClient(timeout=None, follow_redirects=True) as c:
            async with c.stream("GET", asset.url) as resp:
                resp.raise_for_status()
                with open(out, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=64 * 1024):
                        f.write(chunk)
        return out


def _parse_release(data: dict) -> ReleaseInfo:
    tag = str(data.get("tag_name") or "")
    version = tag.lstrip("vV")
    assets = tuple(
        ReleaseAsset(
            name=str(a.get("name") or ""),
            url=str(a.get("browser_download_url") or ""),
            size=int(a.get("size") or 0),
        )
        for a in data.get("assets") or []
        if a.get("browser_download_url")
    )
    return ReleaseInfo(
        version=version,
        tag=tag,
        html_url=str(data.get("html_url") or ""),
        body=str(data.get("body") or ""),
        assets=assets,
    )
