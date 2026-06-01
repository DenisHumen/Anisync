# Contributing (humans & AI agents)

Anisync is designed so future agents can extend it safely. Please follow
these rules.

## Golden rules

1. **Read the docs first.** [ARCHITECTURE.md](ARCHITECTURE.md) is the
   source of truth for layering. Do not let UI call providers directly —
   always go through `core`.
2. **Plugins only.** New sites go in `anisync/providers/`. New embed
   hosts go in `anisync/players/`. Never touch UI to add a site.
3. **No network in tests.** Use `tests/fixtures/` HTML snapshots and
   `httpx.MockTransport`. CI runs offline.
4. **Update docs in the same change.** New page → update [UI.md](UI.md).
   New plugin contract field → update [PROVIDERS.md](PROVIDERS.md) /
   [PLAYERS.md](PLAYERS.md). Mark items done in [ROADMAP.md](ROADMAP.md).
5. **Type hints everywhere.** `from __future__ import annotations` is on.
6. **Style via theme tokens.** No hardcoded colors in widgets.

## Local workflow

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q                 # must pass
python -m anisync         # smoke-launch the GUI
```

## Adding a provider — 5 steps

See [PROVIDERS.md](PROVIDERS.md). TL;DR:

1. `anisync/providers/<id>.py` with `@register_provider` class.
2. Add import in `anisync/providers/__init__.py`.
3. Sample HTML in `tests/fixtures/<id>/`.
4. `tests/test_provider_<id>.py` with `httpx.MockTransport`.
5. Tick the checkbox in [ROADMAP.md](ROADMAP.md).

## Adding a player resolver — 5 steps

See [PLAYERS.md](PLAYERS.md).

## Commit messages

`feat(provider): add anilibria`, `fix(kodik): handle missing hls`, etc.

## When stuck

- The failing test name usually points at the broken layer.
- For UI regressions, run `python -m anisync --debug` to enable Qt
  warnings and `QT_LOGGING_RULES="*=true"`.
- Open `library.db` with `sqlite3 ~/.anisync/library.db` to inspect state.
