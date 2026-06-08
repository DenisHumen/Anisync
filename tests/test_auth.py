"""Auth service tests — offline-mode error + local account persistence."""
from __future__ import annotations

import json

import httpx
import pytest

from anisync.core.auth import Account, AuthError, AuthService
from anisync.utils import paths


@pytest.fixture
def tmp_account(tmp_path, monkeypatch):
    """Redirect ``data_dir()`` at the source so ``_account_path()`` follows."""
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path)
    # auth.py imports data_dir directly; patch its binding too
    from anisync.core import auth as auth_mod
    monkeypatch.setattr(auth_mod, "data_dir", lambda: tmp_path)
    yield tmp_path


async def test_offline_register_raises():
    svc = AuthService(backend_url="")
    assert svc.is_configured is False
    with pytest.raises(AuthError):
        await svc.register("user", "u@x", "pw")


async def test_offline_login_raises():
    svc = AuthService("")
    with pytest.raises(AuthError):
        await svc.login("user", "pw")


def test_save_and_load_account(tmp_account):
    acc = Account(username="alice", token="tok", email="a@x")
    AuthService.save_account(acc)
    loaded = AuthService.current_account()
    assert loaded is not None
    assert loaded.username == "alice"
    assert loaded.token == "tok"


def test_sign_out_removes_file(tmp_account):
    AuthService.save_account(Account(username="a", token="t"))
    assert AuthService.current_account() is not None
    AuthService.sign_out()
    assert AuthService.current_account() is None


def test_corrupt_account_returns_none(tmp_account):
    (tmp_account / "account.json").write_text("not json", "utf-8")
    assert AuthService.current_account() is None
