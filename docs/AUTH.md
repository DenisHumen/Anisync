# Authentication

Anisync's account system is **forward-looking**: the UI and HTTP client
are wired today, but the remote backend is not yet deployed. The app
runs entirely offline and the local SQLite library is the source of
truth for favourites, lists and history.

## Architecture

```
┌─────────────┐    HTTPS    ┌────────────────────┐
│  AuthPage   │  ────────▶  │  AuthService       │
│  (PySide6)  │             │  POST /auth/login  │
└─────────────┘             │  POST /auth/register│
                            └─────────┬──────────┘
                                      ▼
                            ┌────────────────────┐
                            │ data_dir/account.json│
                            │ {username, token}  │
                            └────────────────────┘
```

`Config.auth_backend_url` ("" by default) controls the base URL. When
empty, `AuthService.is_configured` returns `False` and any
`login` / `register` call raises `AuthError` with a friendly "offline
mode" message that the UI surfaces in a glass banner.

## Endpoints (planned)

| Method | Path             | Body                          | Response             |
|--------|------------------|-------------------------------|----------------------|
| POST   | `/auth/register` | `{username,email,password}`   | `{token,username,email}` |
| POST   | `/auth/login`    | `{username,password}`         | `{token,username,email}` |

Tokens are stored locally in `<data_dir>/account.json`. The library
also creates a single `users` row (username `local`) used as the FK for
favourites / history. When real auth ships, that row will be linked to
the remote `username` so cloud sync becomes a one-way merge.

## Status indicators

* `is_configured == False`: UI shows "Cloud accounts are coming soon —
  this build runs in offline mode."
* `AuthError` raised: status label below the form shows the message.

## Tests

`tests/test_auth.py` covers:

* offline mode raises `AuthError` for both endpoints,
* `save_account` → `current_account` roundtrip,
* `sign_out` removes the file,
* corrupt `account.json` returns `None` instead of throwing.
