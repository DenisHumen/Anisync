"""Self-update target detection across platforms (no actual swapping)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from anisync.core import selfupdate


def test_not_frozen_has_no_target(monkeypatch):
    monkeypatch.setattr(selfupdate.sys, "frozen", False, raising=False)
    assert selfupdate.installed_target() is None
    assert selfupdate.can_self_update() is False


def test_macos_target_is_app_bundle(monkeypatch):
    monkeypatch.setattr(selfupdate.sys, "frozen", True, raising=False)
    monkeypatch.setattr(selfupdate.sys, "platform", "darwin")
    monkeypatch.setattr(
        selfupdate.sys, "executable",
        "/Applications/Anisync.app/Contents/MacOS/Anisync",
    )
    assert selfupdate.installed_target() == Path("/Applications/Anisync.app")


@pytest.mark.skipif(
    not sys.platform.startswith("win"),
    reason="pathlib.Path only parses Windows paths on Windows hosts",
)
def test_windows_target_is_install_dir(monkeypatch):
    monkeypatch.setattr(selfupdate.sys, "frozen", True, raising=False)
    monkeypatch.setattr(selfupdate.sys, "platform", "win32")
    monkeypatch.setattr(
        selfupdate.sys, "executable", r"C:\Program Files\Anisync\Anisync.exe"
    )
    assert selfupdate.installed_target() == Path(r"C:\Program Files\Anisync")


def test_linux_target_is_appimage(monkeypatch):
    monkeypatch.setattr(selfupdate.sys, "frozen", True, raising=False)
    monkeypatch.setattr(selfupdate.sys, "platform", "linux")
    monkeypatch.setenv("APPIMAGE", "/home/u/Apps/Anisync.AppImage")
    assert selfupdate.installed_target() == Path("/home/u/Apps/Anisync.AppImage")


def test_linux_without_appimage_env_has_no_target(monkeypatch):
    monkeypatch.setattr(selfupdate.sys, "frozen", True, raising=False)
    monkeypatch.setattr(selfupdate.sys, "platform", "linux")
    monkeypatch.delenv("APPIMAGE", raising=False)
    assert selfupdate.installed_target() is None
