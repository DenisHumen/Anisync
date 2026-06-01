"""Typed exceptions raised by core / providers / players."""
from __future__ import annotations


class AnisyncError(Exception):
    """Base for all Anisync errors."""


class ProviderError(AnisyncError):
    """Generic provider failure (network, HTTP status, etc.)."""


class ProviderParseError(ProviderError):
    """Provider received a response it could not parse — usually a site change."""


class ResolveError(AnisyncError):
    """Player resolver could not turn an embed URL into a stream."""


class DownloadError(AnisyncError):
    """Download manager failure."""


class LibraryError(AnisyncError):
    """Local SQLite library failure."""
