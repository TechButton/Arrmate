# Authentication

Arrmate includes optional authentication to protect your web UI and API. It is **disabled by default** — all pages are accessible without login until you create credentials.

## Setup

1. Navigate to **Settings** in the web UI (`/web/settings`)
2. Enter a username and password
3. Authentication is immediately active

You'll be automatically logged in after creating credentials. All other sessions (browsers, tabs) will be redirected to the login page.

## How It Works

- **Web UI**: Uses signed session cookies (24-hour TTL, HttpOnly, SameSite=Lax)
- **API**: Uses HTTP Basic Auth when authentication is enabled
- **Credentials**: Stored in `auth.json` with bcrypt-hashed passwords
- **Health check**: The `/health` endpoint is always accessible without authentication

## Managing Authentication

From the Settings page you can:

| Action | Effect |
|--------|--------|
| **Create credentials** | Enables authentication with a username and password |
| **Change password** | Updates the password for the existing user |
| **Disable** | Turns off login requirement but keeps credentials stored |
| **Re-enable** | Turns login requirement back on using stored credentials |
| **Delete credentials** | Removes all credentials and returns to fully open mode |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | (auto-generated) | Secret key for signing session cookies. Set this for persistent sessions across container restarts |
| `AUTH_DATA_DIR` | `/data` | Directory where `auth.json` is stored. Should be a persistent volume in Docker |

## Docker Setup

When running in Docker, make sure the `AUTH_DATA_DIR` is on a persistent volume so credentials survive container restarts:

```yaml
services:
  arrmate:
    volumes:
      - arrmate_data:/data    # auth.json is stored here
```

For persistent sessions across restarts, set a `SECRET_KEY` in your `.env`:

```bash
SECRET_KEY=some-random-string-here
```

Without a `SECRET_KEY`, one is auto-generated at startup, meaning all sessions are invalidated when the container restarts.

## API Authentication

When authentication is enabled, API endpoints require HTTP Basic Auth:

```bash
# With auth enabled
curl -u username:password http://localhost:8000/api/v1/services

# Health check is always open
curl http://localhost:8000/health
```

When authentication is disabled, API endpoints are open (no credentials needed).

## Recovery

If you're locked out:

1. Delete the `auth.json` file from your data directory (default: `/data`)
2. Restart Arrmate
3. All pages will be accessible again without login
4. Go to Settings to create new credentials if desired

In Docker:

```bash
docker compose exec arrmate rm /data/auth.json
docker compose restart arrmate
```

## Security Notes

- Passwords are hashed with bcrypt before storage
- Session cookies are cryptographically signed with `itsdangerous`
- The `auth.json` file is written with `0600` permissions (owner read/write only)
- Redirect URLs are validated to prevent open redirect attacks
- This is single-user authentication designed for home/self-hosted use

---

Back to [Documentation](README.md) | [README](../README.md)
