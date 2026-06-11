"""SQLite-backed library: users, favorites, history, downloads.

Single-writer design: all access goes through :class:`LibraryService` which
opens a thread-safe :class:`sqlite3.Connection` (``check_same_thread=False``)
and serializes writes with a lock. Plenty for a single-user desktop app.
"""
from __future__ import annotations

import sqlite3
import threading
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from anisync.core.models import (
    Anime,
    AnimeSummary,
    DownloadStatus,
    DownloadTask,
    Episode,
    HistoryEntry,
    ListKind,
)
from anisync.utils.paths import library_db_path


_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    username  TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS anime_cache (
    provider_id   TEXT NOT NULL,
    url           TEXT NOT NULL,
    title         TEXT NOT NULL,
    poster_url    TEXT,
    year          INTEGER,
    episodes_count INTEGER,
    type          TEXT,
    updated_at    TEXT NOT NULL,
    PRIMARY KEY (provider_id, url)
);

CREATE TABLE IF NOT EXISTS list_entries (
    user_id      INTEGER NOT NULL,
    provider_id  TEXT NOT NULL,
    anime_url    TEXT NOT NULL,
    list_kind    TEXT NOT NULL,
    added_at     TEXT NOT NULL,
    PRIMARY KEY (user_id, provider_id, anime_url, list_kind),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS history (
    user_id          INTEGER NOT NULL,
    provider_id      TEXT NOT NULL,
    anime_url        TEXT NOT NULL,
    episode_number   INTEGER NOT NULL,
    position_seconds INTEGER NOT NULL DEFAULT 0,
    duration_seconds INTEGER NOT NULL DEFAULT 0,
    watched_at       TEXT NOT NULL,
    PRIMARY KEY (user_id, provider_id, anime_url, episode_number)
);

CREATE TABLE IF NOT EXISTS anime_full_cache (
    provider_id    TEXT NOT NULL,
    url            TEXT NOT NULL,
    anime_json     TEXT NOT NULL,
    episodes_json  TEXT NOT NULL,
    updated_at     TEXT NOT NULL,
    PRIMARY KEY (provider_id, url)
);

CREATE TABLE IF NOT EXISTS downloads (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id     TEXT NOT NULL,
    anime_url       TEXT NOT NULL,
    anime_title     TEXT NOT NULL,
    episode_number  INTEGER NOT NULL,
    embed_url       TEXT NOT NULL,
    quality         TEXT NOT NULL,
    file_path       TEXT NOT NULL,
    status          TEXT NOT NULL,
    progress        REAL NOT NULL DEFAULT 0,
    error           TEXT,
    created_at      TEXT NOT NULL
);
"""


def _now() -> str:
    # Naive UTC (matches the historical on-disk format); utcnow() is
    # deprecated from Python 3.12 so derive it from an aware value instead.
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


class LibraryService:
    def __init__(self, db_path: Path | None = None) -> None:
        self._path = db_path or library_db_path()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._lock = threading.RLock()
        self._init_schema()
        self._default_user_id = self._ensure_default_user()

    # ─── setup ────────────────────────────────────────────────────────────

    def _init_schema(self) -> None:
        with self._lock, self._conn:
            self._conn.executescript(_SCHEMA)

    def _ensure_default_user(self) -> int:
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT id FROM users WHERE username = ?", ("local",)
            ).fetchone()
            if row:
                return int(row["id"])
            cur = self._conn.execute(
                "INSERT INTO users (username, created_at) VALUES (?, ?)",
                ("local", _now()),
            )
            return int(cur.lastrowid)

    @property
    def default_user_id(self) -> int:
        return self._default_user_id

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ─── anime cache ──────────────────────────────────────────────────────

    def cache_anime(self, a: Anime | AnimeSummary) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO anime_cache
                    (provider_id, url, title, poster_url, year, episodes_count, type, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (provider_id, url) DO UPDATE SET
                    title = excluded.title,
                    poster_url = excluded.poster_url,
                    year = excluded.year,
                    episodes_count = excluded.episodes_count,
                    type = excluded.type,
                    updated_at = excluded.updated_at
                """,
                (
                    a.provider_id, a.url, a.title, a.poster_url,
                    a.year, a.episodes_count, a.type, _now(),
                ),
            )

    def get_cached(self, provider_id: str, url: str) -> AnimeSummary | None:
        row = self._conn.execute(
            "SELECT * FROM anime_cache WHERE provider_id=? AND url=?",
            (provider_id, url),
        ).fetchone()
        if not row:
            return None
        return AnimeSummary(
            provider_id=row["provider_id"], url=row["url"], title=row["title"],
            poster_url=row["poster_url"], year=row["year"],
            episodes_count=row["episodes_count"], type=row["type"],
        )

    # ─── full anime + episodes cache (for instant details page) ──────────

    def cache_anime_full(self, anime: Anime, episodes: list[Episode]) -> None:
        """Persist a full anime payload + episodes for instant re-open."""
        anime_d = asdict(anime)
        # tuples → lists for JSON; we restore tuples on load
        anime_d["genres"] = list(anime_d.get("genres") or ())
        anime_d["studios"] = list(anime_d.get("studios") or ())
        anime_d["dubs"] = list(anime_d.get("dubs") or ())
        episodes_d = [asdict(e) for e in episodes]
        with self._lock, self._conn:
            self._conn.execute(
                """INSERT INTO anime_full_cache
                     (provider_id, url, anime_json, episodes_json, updated_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT (provider_id, url) DO UPDATE SET
                     anime_json = excluded.anime_json,
                     episodes_json = excluded.episodes_json,
                     updated_at = excluded.updated_at""",
                (
                    anime.provider_id, anime.url,
                    json.dumps(anime_d, ensure_ascii=False),
                    json.dumps(episodes_d, ensure_ascii=False),
                    _now(),
                ),
            )

    def get_cached_full(
        self, provider_id: str, url: str
    ) -> tuple[Anime, list[Episode], datetime] | None:
        row = self._conn.execute(
            """SELECT anime_json, episodes_json, updated_at
                 FROM anime_full_cache WHERE provider_id=? AND url=?""",
            (provider_id, url),
        ).fetchone()
        if not row:
            return None
        try:
            a = json.loads(row["anime_json"])
            a["genres"] = tuple(a.get("genres") or ())
            a["studios"] = tuple(a.get("studios") or ())
            a["dubs"] = tuple(a.get("dubs") or ())
            anime = Anime(**a)
            eps = [Episode(**e) for e in json.loads(row["episodes_json"])]
            updated = datetime.fromisoformat(row["updated_at"])
            return anime, eps, updated
        except Exception:
            return None

    # ─── favorites / lists ────────────────────────────────────────────────

    def add_to_list(
        self,
        anime: Anime | AnimeSummary,
        kind: ListKind,
        *,
        user_id: int | None = None,
    ) -> None:
        self.cache_anime(anime)
        uid = user_id or self._default_user_id
        with self._lock, self._conn:
            self._conn.execute(
                """INSERT OR IGNORE INTO list_entries
                   (user_id, provider_id, anime_url, list_kind, added_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (uid, anime.provider_id, anime.url, kind.value, _now()),
            )

    def remove_from_list(
        self,
        provider_id: str,
        anime_url: str,
        kind: ListKind,
        *,
        user_id: int | None = None,
    ) -> None:
        uid = user_id or self._default_user_id
        with self._lock, self._conn:
            self._conn.execute(
                """DELETE FROM list_entries
                   WHERE user_id=? AND provider_id=? AND anime_url=? AND list_kind=?""",
                (uid, provider_id, anime_url, kind.value),
            )

    def is_in_list(
        self,
        provider_id: str,
        anime_url: str,
        kind: ListKind,
        *,
        user_id: int | None = None,
    ) -> bool:
        uid = user_id or self._default_user_id
        row = self._conn.execute(
            """SELECT 1 FROM list_entries
               WHERE user_id=? AND provider_id=? AND anime_url=? AND list_kind=?""",
            (uid, provider_id, anime_url, kind.value),
        ).fetchone()
        return row is not None

    def list_anime(
        self, kind: ListKind, *, user_id: int | None = None
    ) -> list[AnimeSummary]:
        uid = user_id or self._default_user_id
        rows = self._conn.execute(
            """SELECT c.* FROM list_entries e
               JOIN anime_cache c
                 ON c.provider_id = e.provider_id AND c.url = e.anime_url
               WHERE e.user_id = ? AND e.list_kind = ?
               ORDER BY e.added_at DESC""",
            (uid, kind.value),
        ).fetchall()
        return [
            AnimeSummary(
                provider_id=r["provider_id"], url=r["url"], title=r["title"],
                poster_url=r["poster_url"], year=r["year"],
                episodes_count=r["episodes_count"], type=r["type"],
            )
            for r in rows
        ]

    # ─── history ──────────────────────────────────────────────────────────

    def record_progress(
        self,
        provider_id: str,
        anime_url: str,
        episode_number: int,
        position_seconds: int,
        duration_seconds: int,
        *,
        user_id: int | None = None,
    ) -> None:
        uid = user_id or self._default_user_id
        with self._lock, self._conn:
            self._conn.execute(
                """INSERT INTO history
                     (user_id, provider_id, anime_url, episode_number,
                      position_seconds, duration_seconds, watched_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT (user_id, provider_id, anime_url, episode_number)
                   DO UPDATE SET
                     position_seconds = excluded.position_seconds,
                     duration_seconds = excluded.duration_seconds,
                     watched_at = excluded.watched_at
                """,
                (uid, provider_id, anime_url, episode_number,
                 position_seconds, duration_seconds, _now()),
            )

    def list_history(
        self, *, limit: int = 50, user_id: int | None = None
    ) -> list[HistoryEntry]:
        uid = user_id or self._default_user_id
        rows = self._conn.execute(
            """SELECT h.*, c.title, c.poster_url FROM history h
               LEFT JOIN anime_cache c
                 ON c.provider_id = h.provider_id AND c.url = h.anime_url
               WHERE h.user_id = ?
               ORDER BY h.watched_at DESC
               LIMIT ?""",
            (uid, limit),
        ).fetchall()
        return [
            HistoryEntry(
                anime_url=r["anime_url"],
                provider_id=r["provider_id"],
                episode_number=r["episode_number"],
                position_seconds=r["position_seconds"],
                duration_seconds=r["duration_seconds"],
                watched_at=datetime.fromisoformat(r["watched_at"]),
                title=r["title"] or "",
                poster_url=r["poster_url"],
            )
            for r in rows
        ]

    def episodes_watched(
        self, provider_id: str, anime_url: str, *, user_id: int | None = None
    ) -> set[int]:
        uid = user_id or self._default_user_id
        rows = self._conn.execute(
            """SELECT episode_number FROM history
               WHERE user_id=? AND provider_id=? AND anime_url=?""",
            (uid, provider_id, anime_url),
        ).fetchall()
        return {int(r["episode_number"]) for r in rows}

    # ─── downloads ────────────────────────────────────────────────────────

    def add_download(self, task: DownloadTask) -> int:
        with self._lock, self._conn:
            cur = self._conn.execute(
                """INSERT INTO downloads
                     (provider_id, anime_url, anime_title, episode_number,
                      embed_url, quality, file_path, status, progress,
                      error, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (task.provider_id, task.anime_url, task.anime_title,
                 task.episode_number, task.embed_url, task.quality,
                 task.file_path, task.status.value, task.progress,
                 task.error, task.created_at.isoformat()),
            )
            task.id = int(cur.lastrowid)
            return task.id

    def update_download(self, task: DownloadTask) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """UPDATE downloads SET status=?, progress=?, error=?, file_path=?
                   WHERE id=?""",
                (task.status.value, task.progress, task.error,
                 task.file_path, task.id),
            )

    def list_downloads(self) -> list[DownloadTask]:
        rows = self._conn.execute(
            "SELECT * FROM downloads ORDER BY created_at DESC"
        ).fetchall()
        out: list[DownloadTask] = []
        for r in rows:
            out.append(DownloadTask(
                id=int(r["id"]),
                provider_id=r["provider_id"],
                anime_url=r["anime_url"],
                anime_title=r["anime_title"],
                episode_number=int(r["episode_number"]),
                embed_url=r["embed_url"],
                quality=r["quality"],
                file_path=r["file_path"],
                status=DownloadStatus(r["status"]),
                progress=float(r["progress"]),
                error=r["error"],
                created_at=datetime.fromisoformat(r["created_at"]),
            ))
        return out

    def delete_download(self, task_id: int) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM downloads WHERE id=?", (task_id,))


# ─── module-level singleton ────────────────────────────────────────────────

_service: LibraryService | None = None


def get_library() -> LibraryService:
    global _service
    if _service is None:
        _service = LibraryService()
    return _service


def reset_library_for_tests(path: Path) -> LibraryService:
    """Helper used only by tests."""
    global _service
    if _service is not None:
        try:
            _service.close()
        except Exception:  # pragma: no cover
            pass
    _service = LibraryService(path)
    return _service
