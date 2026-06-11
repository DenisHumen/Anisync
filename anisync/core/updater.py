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
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable

import httpx

import anisync

log = logging.getLogger(__name__)

GITHUB_REPO = "DenisHumen/Anisync"  # override via Config.update_repo

# Report download progress at most every this many bytes.
_PROGRESS_STEP = 256 * 1024


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
    body: str               # release notes (GitHub markdown)
    assets: tuple[ReleaseAsset, ...]
    published_at: datetime | None = None
    prerelease: bool = False

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


def is_newer(remote: str, local: str | None = None) -> bool:
    # Resolve the running version at *call* time — a module-level default
    # would freeze whatever __version__ was at import.
    return parse_version(remote) > parse_version(local or anisync.__version__)


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

    async def releases(self, *, limit: int = 10) -> list[ReleaseInfo]:
        """Release history (newest first). Drafts and prereleases are
        skipped. Returns ``[]`` on any network/API problem — callers show
        a friendly offline state instead of crashing."""
        url = f"https://api.github.com/repos/{self._repo}/releases"
        try:
            async with httpx.AsyncClient(
                timeout=10, headers={"Accept": "application/vnd.github+json"}
            ) as c:
                r = await c.get(url, params={"per_page": limit})
        except httpx.HTTPError as e:
            log.info("Updater offline: %s", e)
            return []
        if r.status_code >= 400:
            log.info("Updater releases HTTP %s", r.status_code)
            return []
        try:
            data = r.json()
        except ValueError:
            return []
        if not isinstance(data, list):
            return []
        return [
            _parse_release(item)
            for item in data
            if isinstance(item, dict)
            and not item.get("draft")
            and not item.get("prerelease")
        ]

    async def check_with_news(
        self,
    ) -> tuple[ReleaseInfo, list[ReleaseInfo]] | None:
        """Newest release if newer than the running version, together with
        **every** release the user has missed (newest first) so the update
        dialog can show the full "what you get" changelog."""
        rels = await self.releases(limit=15)
        if rels:
            newer = [r for r in rels if is_newer(r.version)]
            if not newer:
                return None
            newer.sort(key=lambda r: parse_version(r.version), reverse=True)
            return newer[0], newer
        # List endpoint failed (offline / rate-limited) — fall back to the
        # single /latest probe so updates still surface.
        rel = await self.check()
        return (rel, [rel]) if rel else None

    async def download_asset(
        self,
        asset: ReleaseAsset,
        dest_dir: Path,
        progress: Callable[[int, int], None] | None = None,
    ) -> Path:
        """Stream ``asset`` into ``dest_dir`` and return the file path.

        ``progress(done_bytes, total_bytes)`` is invoked from the download
        thread (throttled); ``total_bytes`` may be 0 when unknown. The file
        is written to ``*.part`` and renamed at the end so an interrupted
        download never leaves a plausible-looking installer behind.
        """
        dest_dir.mkdir(parents=True, exist_ok=True)
        out = dest_dir / asset.name
        part = out.with_name(out.name + ".part")
        done = 0
        last_report = 0
        async with httpx.AsyncClient(timeout=None, follow_redirects=True) as c:
            async with c.stream("GET", asset.url) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("Content-Length") or 0) or asset.size
                with open(part, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=64 * 1024):
                        f.write(chunk)
                        done += len(chunk)
                        if progress and done - last_report >= _PROGRESS_STEP:
                            last_report = done
                            progress(done, total)
        part.replace(out)
        if progress and last_report != done:
            progress(done, total or done)
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
    raw_date = data.get("published_at") or data.get("created_at") or ""
    published: datetime | None = None
    if raw_date:
        try:
            published = datetime.fromisoformat(str(raw_date).replace("Z", "+00:00"))
        except ValueError:
            published = None
    return ReleaseInfo(
        version=version,
        tag=tag,
        html_url=str(data.get("html_url") or ""),
        body=str(data.get("body") or ""),
        assets=assets,
        published_at=published,
        prerelease=bool(data.get("prerelease")),
    )


def compose_release_notes_md(
    releases: Iterable[ReleaseInfo],
    *,
    current_version: str | None = None,
) -> str:
    """Markdown digest of releases (newest first) for the update /
    changelog dialogs: version + date heading, then the GitHub release
    notes. When ``current_version`` is given, entries are badged as
    *new* (newer than installed) or *installed* (the running build)."""
    cur = parse_version(current_version) if current_version else None
    chunks: list[str] = []
    for r in releases:
        title = r.tag or f"v{r.version}"
        meta: list[str] = []
        if r.published_at:
            meta.append(r.published_at.strftime("%d %b %Y"))
        if cur is not None:
            v = parse_version(r.version)
            if v == cur:
                meta.append("installed")
            elif v > cur:
                meta.append("new")
        head = f"### {title}" + (f"  ·  {'  ·  '.join(meta)}" if meta else "")
        body = (r.body or "").strip() or "_No release notes._"
        chunks.append(f"{head}\n\n{body}")
    return "\n\n---\n\n".join(chunks) or "_No releases published yet._"
