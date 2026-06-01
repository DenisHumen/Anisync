"""Stub auth service backed by a future remote registration backend.

Currently no real backend exists. The :class:`AuthService` already wires
through ``httpx`` so when the backend is deployed all that changes is
``Config.auth_backend_url``. Until then ``login`` / ``register`` raise
:class:`AuthError` with a clear "Backend offline" message and the UI
shows a friendly placeholder.

The local SQLite ``users`` table created by the library remains the
single source of truth for *local* user_id used by favorites/history.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx

from anisync.core.errors import AnisyncError
from anisync.utils.paths import data_dir


class AuthError(AnisyncError):
    """Authentication / registration failure (network, bad creds, ...)."""


@dataclass
class Account:
    username: str
    token: str
    email: str | None = None


def _account_path() -> Path:
    return data_dir() / "account.json"


class AuthService:
    """Thin wrapper around the registration backend HTTP API.

    Endpoints (planned):

      POST /auth/register  {username, email, password}  → {token, ...}
      POST /auth/login     {username, password}         → {token, ...}
      GET  /auth/me        Authorization: Bearer <t>    → {username, ...}
    """

    def __init__(self, backend_url: str | None = None) -> None:
        self._backend_url = (backend_url or "").rstrip("/")

    @property
    def is_configured(self) -> bool:
        return bool(self._backend_url)

    # ── persistence (local) ──────────────────────────────────────────────

    @staticmethod
    def current_account() -> Account | None:
        p = _account_path()
        if not p.exists():
            return None
        try:
            data = json.loads(p.read_text("utf-8"))
            return Account(**data)
        except Exception:
            return None

    @staticmethod
    def save_account(acc: Account) -> None:
        _account_path().write_text(json.dumps(asdict(acc)), "utf-8")

    @staticmethod
    def sign_out() -> None:
        p = _account_path()
        if p.exists():
            p.unlink()

    # ── remote (HTTP) ────────────────────────────────────────────────────

    async def register(self, username: str, email: str, password: str) -> Account:
        return await self._post("/auth/register",
                                {"username": username, "email": email, "password": password})

    async def login(self, username: str, password: str) -> Account:
        return await self._post("/auth/login",
                                {"username": username, "password": password})

    async def _post(self, path: str, payload: dict[str, Any]) -> Account:
        if not self.is_configured:
            raise AuthError(
                "Registration backend is not configured yet. "
                "This build runs in offline mode — your library is stored locally."
            )
        url = self._backend_url + path
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.post(url, json=payload)
        except httpx.HTTPError as e:
            raise AuthError(f"Cannot reach auth server: {e}") from e
        if r.status_code == 401:
            raise AuthError("Invalid username or password.")
        if r.status_code == 409:
            raise AuthError("Username or email already taken.")
        if r.status_code >= 400:
            raise AuthError(f"Server error ({r.status_code}).")
        try:
            data = r.json()
        except ValueError as e:
            raise AuthError("Malformed response from server.") from e
        token = data.get("token")
        if not token:
            raise AuthError("Server did not return an auth token.")
        acc = Account(username=data.get("username") or payload.get("username", ""),
                      token=token,
                      email=data.get("email"))
        self.save_account(acc)
        return acc
