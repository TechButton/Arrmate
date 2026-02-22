# Authentication

Off by default. All pages and API routes are open until you create credentials.

## Setup

Go to Settings (`/web/settings`), enter a username and password. That's it — authentication activates immediately and you'll stay logged in.

## Managing credentials

From the Settings page:

| Action | Effect |
|--------|--------|
| Create credentials | Enables login with the chosen username/password |
| Change password | Updates the password, keeps the same username |
| Disable | Turns off the login requirement without deleting credentials |
| Re-enable | Turns login back on using the stored credentials |
| Delete credentials | Wipes everything, returns to fully open mode |

## Sessions and persistence

Session cookies are signed with `SECRET_KEY`. If that env var isn't set, a key is generated at startup — meaning all sessions become invalid on container restart.

For persistent sessions, set a `SECRET_KEY` in your `.env`:

```bash
SECRET_KEY=some-long-random-string
```

## API authentication

When enabled, API requests use HTTP Basic Auth:

```bash
curl -u username:password http://localhost:8000/api/v1/services
```

`/health` is always open regardless of auth state.

## Recovery

Delete `auth.json` from the data directory and restart:

```bash
docker compose exec arrmate rm /data/auth.json
docker compose restart arrmate
```

## Notes

- Passwords are bcrypt-hashed before storage
- `auth.json` is written with 0600 permissions
- Session cookies are HttpOnly, SameSite=Lax, signed with itsdangerous
- Single-user — designed for personal/home use
