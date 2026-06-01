"""TOML-backed app config (`~/.../Anisync/config.toml`)."""
from __future__ import annotations

import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path

from anisync.utils.paths import config_path, default_downloads_dir


@dataclass(slots=True)
class Config:
    downloads_dir: str = field(default_factory=lambda: str(default_downloads_dir()))
    max_concurrent_downloads: int = 2
    preferred_quality: str = "best"
    preferred_dub: str = ""           # empty = first available
    autoplay_next: bool = True
    theme: str = "dark"
    auth_backend_url: str = ""        # set when remote backend is deployed
    update_repo: str = "anisync/anisync"
    check_updates_on_start: bool = True

    @classmethod
    def load(cls) -> "Config":
        p = config_path()
        if not p.exists():
            cfg = cls()
            cfg.save()
            return cfg
        data = tomllib.loads(p.read_text("utf-8"))
        cfg = cls()
        for k, v in data.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)
        return cfg

    def save(self) -> None:
        p: Path = config_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        # tiny manual TOML writer (stdlib only)
        lines: list[str] = []
        for k, v in asdict(self).items():
            if isinstance(v, str):
                lines.append(f'{k} = "{v}"')
            elif isinstance(v, bool):
                lines.append(f"{k} = {str(v).lower()}")
            else:
                lines.append(f"{k} = {v}")
        p.write_text("\n".join(lines) + "\n", "utf-8")
