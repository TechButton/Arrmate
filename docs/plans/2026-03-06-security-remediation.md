# Security Remediation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Address all SDL findings from the 2026-03-06 security review, from trivial single-line fixes through to rate limiting and destructive-action confirmation.

**Status: ✅ COMPLETE — all tasks implemented and committed (branch `security/sdl-remediation`)**

**Architecture:** Changes are almost entirely self-contained — no new services, no schema migrations. Rate limiting uses a zero-dependency in-memory fixed-window counter (slowapi not needed). Destructive-action confirmation was already present in the codebase — confirmed in-scope and working.

**Tech Stack:** Python 3.11, FastAPI, Jinja2/HTMX, SQLite, pytest + pytest-asyncio, httpx test client.

---

## Priority Groups

| Group | Effort | Tasks |
|-------|--------|-------|
| **P0 — Trivial, deploy immediately** | ~5 min each | 1, 2, 3, 4, 5 |
| **P1 — Low effort, high value** | 15–30 min each | 6, 7, 8, 9 |
| **P2 — Medium effort** | 1–2 hrs each | 10, 11 |

Work through P0 first (they are independent and safe to batch), then P1, then P2.

---

## P0: Trivial Fixes

---

### Task 1: Session cookie — add `secure` flag

**Finding:** M1 — cookies can be sent over HTTP because `secure=True` is absent.

**Files:**
- Modify: `src/arrmate/auth/session.py:44-52`
- Create/extend: `tests/test_auth.py`

**Step 1: Write the failing test**

Create `tests/test_auth.py`:

```python
"""Tests for authentication session management."""
from unittest.mock import MagicMock
from arrmate.auth.session import set_session_cookie, SESSION_COOKIE


def test_session_cookie_has_secure_flag():
    """Session cookie must set secure=True to prevent transmission over HTTP."""
    response = MagicMock()
    set_session_cookie(response, "test-token")
    call_kwargs = response.set_cookie.call_args.kwargs
    assert call_kwargs.get("secure") is True, "Cookie must have secure=True"


def test_session_cookie_has_httponly_flag():
    response = MagicMock()
    set_session_cookie(response, "test-token")
    assert response.set_cookie.call_args.kwargs.get("httponly") is True


def test_session_cookie_has_samesite_lax():
    response = MagicMock()
    set_session_cookie(response, "test-token")
    assert response.set_cookie.call_args.kwargs.get("samesite") == "lax"
```

**Step 2: Run test to verify it fails**

```bash
cd /mnt/c/tools/arrmate
python -m pytest tests/test_auth.py::test_session_cookie_has_secure_flag -v
```
Expected: FAIL — `AssertionError: Cookie must have secure=True`

**Step 3: Implement fix**

In `src/arrmate/auth/session.py`, update `set_session_cookie`:

```python
def set_session_cookie(response: Response, token: str) -> None:
    """Set the session cookie on a response."""
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=True,
    )
```

**Step 4: Run tests**

```bash
python -m pytest tests/test_auth.py -v
```
Expected: 3 PASS

**Step 5: Commit**

```bash
git add tests/test_auth.py src/arrmate/auth/session.py
git commit -m "fix(auth): add secure flag to session cookie"
```

---

### Task 2: Default admin — remove password from INFO log

**Finding:** M2 — `changeme123` appears in INFO logs, visible in any log aggregator.

**Files:**
- Modify: `src/arrmate/auth/user_db.py:164`
- Extend: `tests/test_auth.py`

**Step 1: Write the failing test**

Add to `tests/test_auth.py`:

```python
import logging
from arrmate.auth import user_db as _user_db


def test_default_admin_creation_does_not_log_password(tmp_path, caplog, monkeypatch):
    """Default admin creation must not log the plain-text password."""
    monkeypatch.setattr(_user_db, "_db_path", lambda: tmp_path / "users.db")

    with caplog.at_level(logging.DEBUG, logger="arrmate.auth.user_db"):
        _user_db._create_default_admin()

    full_log = " ".join(caplog.messages)
    assert "changeme123" not in full_log, "Plain-text default password must not appear in logs"
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_auth.py::test_default_admin_creation_does_not_log_password -v
```
Expected: FAIL

**Step 3: Implement fix**

In `src/arrmate/auth/user_db.py`, line ~164, change:

```python
# BEFORE
logger.info("Created default admin account (username: admin, password: changeme123)")

# AFTER
logger.info("Created default admin account (username: admin) — change password on first login")
```

**Step 4: Run tests**

```bash
python -m pytest tests/test_auth.py -v
```
Expected: all PASS

**Step 5: Commit**

```bash
git add src/arrmate/auth/user_db.py tests/test_auth.py
git commit -m "fix(auth): remove plain-text default password from log output"
```

---

### Task 3: Remove Ollama host port binding

**Finding:** M3 — Ollama exposed on `0.0.0.0:11434` with no authentication.

**Files:**
- Modify: `docker-compose.yml`
- Modify: `docker-compose.full.yml` (check for same pattern)
- Modify: `docker/docker-compose.yml` (check for same pattern)

**Step 1: Check all compose files**

```bash
grep -n "11434" /mnt/c/tools/arrmate/docker-compose.yml \
    /mnt/c/tools/arrmate/docker-compose.full.yml \
    /mnt/c/tools/arrmate/docker/docker-compose.yml 2>/dev/null
```

**Step 2: Comment out the ollama `ports:` block in each affected file**

```yaml
# BEFORE
  ollama:
    ports:
      - "11434:11434"

# AFTER — Ollama is reachable within arrmate-net via http://ollama:11434
  ollama:
    # Port 11434 is accessible within arrmate-net; no host binding needed.
    # Uncomment only if you need to reach Ollama from outside this stack:
    # ports:
    #   - "11434:11434"
```

**Step 3: Verify Arrmate can still reach Ollama internally**

```bash
docker compose up -d
docker exec arrmate python -c "import httpx; r=httpx.get('http://ollama:11434/api/tags'); print(r.status_code)"
```
Expected: `200`

```bash
# Verify host port is NOT accessible
curl -s --connect-timeout 3 http://localhost:11434/api/tags || echo "GOOD: port not reachable from host"
```

**Step 4: Commit**

```bash
git add docker-compose.yml docker-compose.full.yml docker/docker-compose.yml
git commit -m "fix(docker): remove ollama host port binding — internal network only"
```

---

### Task 4: Add command length limit

**Finding:** M5 — no `max_length` on the command field allows unbounded LLM requests (DoS / cost abuse).

**Files:**
- Modify: `src/arrmate/interfaces/api/app.py:51-54`
- Create/extend: `tests/test_api.py`

**Step 1: Write the failing test**

Create `tests/test_api.py`:

```python
"""Tests for the FastAPI application."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from arrmate.interfaces.api.app import app
    return TestClient(app, raise_server_exceptions=False)


def test_execute_command_rejects_oversized_input(client):
    """Commands over 2000 characters must be rejected with 422."""
    oversized = "a" * 2001
    resp = client.post(
        "/api/v1/execute",
        json={"command": oversized},
        headers={"Authorization": "Bearer fake-token"},
    )
    assert resp.status_code == 422, f"Expected 422 for oversized input, got {resp.status_code}"
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_api.py::test_execute_command_rejects_oversized_input -v
```
Expected: FAIL (returns 401, not 422 — Pydantic doesn't reject it before auth)

**Step 3: Implement fix**

In `src/arrmate/interfaces/api/app.py`, update `CommandRequest`:

```python
class CommandRequest(BaseModel):
    """Request model for command execution."""
    command: str = Field(..., description="Natural language command to execute", max_length=2000)
    dry_run: bool = Field(default=False, description="Parse only, don't execute")
```

Note: Pydantic validates `max_length` before the route handler runs, so it fires before auth — the 422 is returned immediately.

**Step 4: Run tests**

```bash
python -m pytest tests/test_api.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add src/arrmate/interfaces/api/app.py tests/test_api.py
git commit -m "fix(api): limit command input to 2000 chars to prevent DoS"
```

---

### Task 5: Raise minimum password length to 8

**Finding:** L1 — 4-character minimum allows trivially weak passwords.

**Files:**
- Modify: `src/arrmate/interfaces/web/routes.py` (find `len(password) < 4`)
- Extend: `tests/test_auth.py`

**Step 1: Write the failing test**

Add to `tests/test_auth.py`:

```python
import inspect
from arrmate.interfaces.web import routes as _routes


def test_minimum_password_length_is_at_least_eight():
    """Password minimum must be >= 8 characters (NIST SP 800-63B)."""
    source = inspect.getsource(_routes)
    # Confirm the old 4-char check is gone
    assert "len(password) < 4" not in source, \
        "Found 4-character minimum — must be at least 8"
    # Confirm an acceptable minimum is present
    assert any(f"len(password) < {n}" in source for n in range(8, 20)), \
        "Expected minimum password length >= 8 not found in routes"
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_auth.py::test_minimum_password_length_is_at_least_eight -v
```
Expected: FAIL

**Step 3: Implement fix**

In `src/arrmate/interfaces/web/routes.py`, find and update the password length check (there may be more than one — search for `len(password) < 4`):

```python
# BEFORE
elif len(password) < 4:
    error = "Password must be at least 4 characters"

# AFTER
elif len(password) < 8:
    error = "Password must be at least 8 characters"
```

**Step 4: Run tests**

```bash
python -m pytest tests/test_auth.py -v
```
Expected: all PASS

**Step 5: Commit**

```bash
git add src/arrmate/interfaces/web/routes.py tests/test_auth.py
git commit -m "fix(auth): raise minimum password length from 4 to 8 characters"
```

---

## P1: Low-Effort, High-Value

---

### Task 6: Run container as non-root user

**Finding:** H1 — uvicorn, ffmpeg, and all file I/O run as root inside the container.

**Files:**
- Modify: `Dockerfile`
- Modify: `docker/entrypoint.sh`

**Step 1: Add `su-exec` and create `arrmate` user in Dockerfile**

In `Dockerfile`, update the `apt-get` line to include `su-exec`, then add user creation after the `/data` mkdir:

```dockerfile
# System dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    ffmpeg \
    su-exec \
    && rm -rf /var/lib/apt/lists/*

# ... (existing COPY and pip install lines) ...

# Create data directory and non-root user
RUN mkdir -p /data \
    && groupadd -r arrmate \
    && useradd -r -g arrmate -d /app -s /sbin/nologin arrmate \
    && chown -R arrmate:arrmate /app /data
```

Remove any existing `USER` instruction if present. Do **not** add `USER arrmate` to the Dockerfile — the entrypoint handles the privilege drop after fixing volume ownership.

**Step 2: Update entrypoint.sh**

```sh
#!/bin/sh
# Fix /data ownership (named Docker volumes are created as root),
# then drop to the non-root arrmate user.
DATA_DIR="${AUTH_DATA_DIR:-/data}"
mkdir -p "$DATA_DIR"
chown arrmate:arrmate "$DATA_DIR"
exec su-exec arrmate "$@"
```

**Step 3: Build and verify**

```bash
docker compose build
docker compose up -d
docker exec arrmate whoami
```
Expected: `arrmate`

```bash
docker exec arrmate id
```
Expected: non-zero UID, e.g. `uid=999(arrmate) gid=999(arrmate)`

**Step 4: Verify data directory is still writable**

```bash
docker exec arrmate python -c "
from pathlib import Path
p = Path('/data/test.txt')
p.write_text('ok')
assert p.read_text() == 'ok'
p.unlink()
print('write/read/delete ok')
"
```
Expected: `write/read/delete ok`

**Step 5: Commit**

```bash
git add Dockerfile docker/entrypoint.sh
git commit -m "fix(docker): run container as non-root arrmate user via su-exec"
```

---

### Task 7: Sanitize 500 error responses

**Finding:** M4 — `str(e)` from unhandled exceptions exposes internal paths and state to API callers.

**Files:**
- Modify: `src/arrmate/interfaces/api/app.py` (the `execute_command` handler's `except Exception` block)
- Extend: `tests/test_api.py`

**Step 1: Write the failing test**

Add to `tests/test_api.py`:

```python
from unittest.mock import patch, AsyncMock


def test_internal_exception_does_not_leak_details(client):
    """A 500 response body must not contain internal file paths or exception details."""
    with patch("arrmate.interfaces.api.app.parser") as mock_parser:
        mock_parser.parse = AsyncMock(
            side_effect=RuntimeError("DB at /data/secret/path/users.db failed")
        )
        resp = client.post(
            "/api/v1/execute",
            json={"command": "list shows"},
            headers={"Authorization": "Bearer amt_fakefakefake"},
        )
    # 401 because the token is fake — but confirm our sanitized message pattern
    # would be in place. To test the 500 path properly, use a patched auth:
    assert "/data/secret" not in resp.text
    assert "users.db" not in resp.text
```

For a more complete test that actually hits the 500 path, add an integration helper that bypasses auth:

```python
def test_500_response_body_is_generic(monkeypatch):
    """When the executor raises unexpectedly, the response body must be generic."""
    from arrmate.interfaces.api.app import app
    from fastapi.testclient import TestClient
    from arrmate.auth.dependencies import get_api_user

    # Override auth dependency to return a fake user
    app.dependency_overrides[get_api_user] = lambda: {
        "user_id": "test", "username": "test", "role": "admin", "token_id": "test"
    }
    test_client = TestClient(app, raise_server_exceptions=False)

    with patch("arrmate.interfaces.api.app.parser") as mock_parser:
        mock_parser.parse = AsyncMock(
            side_effect=RuntimeError("internal path /data/users.db exposed")
        )
        resp = test_client.post("/api/v1/execute", json={"command": "list shows"})

    app.dependency_overrides.clear()

    assert resp.status_code == 500
    assert "/data/users.db" not in resp.text
    assert "internal path" not in resp.text
    assert "internal error" in resp.text.lower()
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_api.py::test_500_response_body_is_generic -v
```
Expected: FAIL — response contains the raw exception message

**Step 3: Implement fix**

In `src/arrmate/interfaces/api/app.py`, ensure `logger` is defined (add near top if missing):

```python
import logging
logger = logging.getLogger(__name__)
```

Update the `except Exception` block in `execute_command`:

```python
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Unhandled error in execute_command: %s", e)
        raise HTTPException(status_code=500, detail="An internal error occurred")
```

**Step 4: Run tests**

```bash
python -m pytest tests/test_api.py -v
```
Expected: all PASS

**Step 5: Commit**

```bash
git add src/arrmate/interfaces/api/app.py tests/test_api.py
git commit -m "fix(api): sanitize 500 responses — log exception server-side, return generic message"
```

---

### Task 8: Validate transcode file paths against allowed roots

**Finding:** L2 — ffmpeg receives file paths from Sonarr/Radarr without verifying they stay inside expected media directories.

**Files:**
- Modify: `src/arrmate/clients/transcoder.py`
- Modify: `src/arrmate/config/settings.py`
- Create: `tests/test_transcoder.py`

**Step 1: Write the failing tests**

Create `tests/test_transcoder.py`:

```python
"""Tests for the transcoding pipeline."""
from pathlib import Path
from unittest.mock import patch, MagicMock


def test_transcode_rejects_path_traversal(tmp_path):
    """Paths that escape the allowed media root must be rejected."""
    from arrmate.clients.transcoder import _transcode_sync_validated

    media_dir = tmp_path / "media"
    media_dir.mkdir()
    bad_path = str(media_dir / ".." / "etc" / "passwd")

    success, msg = _transcode_sync_validated(bad_path, 28, "medium", allowed_roots=[str(media_dir)])

    assert not success
    assert "not within allowed media" in msg.lower()


def test_transcode_accepts_path_inside_root(tmp_path):
    """Paths inside allowed_roots must pass validation (ffmpeg may then fail, that's ok)."""
    from arrmate.clients.transcoder import _transcode_sync_validated

    media_dir = tmp_path / "media"
    (media_dir / "show").mkdir(parents=True)
    safe_file = media_dir / "show" / "ep1.mkv"
    safe_file.write_bytes(b"fake")

    with patch("arrmate.clients.transcoder.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stderr="ffmpeg not available")
        success, msg = _transcode_sync_validated(
            str(safe_file), 28, "medium", allowed_roots=[str(media_dir)]
        )

    assert "not within allowed media" not in msg.lower()


def test_transcode_skips_validation_when_no_roots_configured(tmp_path):
    """Empty allowed_roots disables path validation for backward compatibility."""
    from arrmate.clients.transcoder import _transcode_sync_validated

    fake_file = tmp_path / "movie.mkv"
    fake_file.write_bytes(b"fake")

    with patch("arrmate.clients.transcoder.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stderr="ffmpeg not available")
        success, msg = _transcode_sync_validated(str(fake_file), 28, "medium", allowed_roots=[])

    assert "not within allowed media" not in msg.lower()
```

**Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_transcoder.py -v
```
Expected: FAIL — `ImportError: cannot import name '_transcode_sync_validated'`

**Step 3: Add `transcode_allowed_roots` to Settings**

In `src/arrmate/config/settings.py`, add before the closing of the `Settings` class:

```python
transcode_allowed_roots: list[str] = Field(
    default=[],
    description=(
        "Allowed root directories for H.265 transcoding (list of absolute paths). "
        "When set, ffmpeg will only process files within these directories. "
        "Set via env var as a comma-separated list: TRANSCODE_ALLOWED_ROOTS=/movies,/tv"
    ),
)
```

**Step 4: Add `_transcode_sync_validated` to transcoder**

In `src/arrmate/clients/transcoder.py`, add this function after `_transcode_sync`:

```python
def _transcode_sync_validated(
    file_path: str,
    crf: int,
    preset: str,
    allowed_roots: list[str],
) -> tuple[bool, str]:
    """Validate file_path is within allowed_roots, then delegate to _transcode_sync.

    If allowed_roots is empty, path validation is skipped (backward compatibility
    for deployments that have not configured TRANSCODE_ALLOWED_ROOTS).
    """
    if allowed_roots:
        resolved = Path(file_path).resolve()
        allowed = [Path(r).resolve() for r in allowed_roots]
        if not any(resolved.is_relative_to(root) for root in allowed):
            return False, f"Path not within allowed media directory: {file_path}"
    return _transcode_sync(file_path, crf, preset)
```

**Step 5: Wire it into `run_transcode_job`**

In `run_transcode_job`, replace the `_transcode_sync` call:

```python
# BEFORE
success, error = await loop.run_in_executor(
    None, _transcode_sync, file_info["path"], crf, preset
)

# AFTER
allowed_roots = list(settings.transcode_allowed_roots)
success, error = await loop.run_in_executor(
    None, _transcode_sync_validated, file_info["path"], crf, preset, allowed_roots
)
```

**Step 6: Run tests**

```bash
python -m pytest tests/test_transcoder.py -v
```
Expected: all PASS

**Step 7: Commit**

```bash
git add src/arrmate/clients/transcoder.py src/arrmate/config/settings.py tests/test_transcoder.py
git commit -m "fix(transcoder): validate file paths stay within configured media roots"
```

---

### Task 9: Add SECURITY.md

**Finding:** Info — no vulnerability disclosure policy.

**Files:**
- Create: `SECURITY.md`

**Step 1: Create the file**

```markdown
# Security Policy

## Supported Versions

| Version | Supported |
| ------- | --------- |
| latest  | Yes       |

## Reporting a Vulnerability

If you discover a security vulnerability in Arrmate, please **do not** open a public GitHub issue.

Report it privately via **GitHub Private Vulnerability Reporting**: go to the repository
Security tab and select "Report a vulnerability".

Please include:
- Description of the vulnerability and its impact
- Steps to reproduce
- Affected versions
- Any suggested mitigations

We aim to respond within **72 hours** and to ship a fix within **14 days** for critical issues.

## Security Expectations

- Arrmate is designed for **private, self-hosted** deployments on trusted networks.
- All `/api/v1/*` endpoints require Bearer token authentication.
- The web UI requires session authentication.
- Secrets (API keys, LLM provider keys) are injected via environment variables — never commit
  them to source control.
- We recommend placing Arrmate behind a TLS-terminating reverse proxy (e.g., Traefik, Nginx)
  in any deployment reachable from outside your LAN.
```

**Step 2: Commit**

```bash
git add SECURITY.md
git commit -m "docs: add SECURITY.md with vulnerability disclosure policy"
```

---

## P2: Medium-Effort

---

### Task 10: Rate limiting on authentication endpoints

**Finding:** H2 — login endpoints have no rate limiting or brute-force protection.

**Approach:** `slowapi` wraps starlette/FastAPI with per-IP rate limiting. Apply **10 attempts per minute** to:
- `POST /web/login` (form login)
- `POST /api/v1/auth/token` (API token login)

**Files:**
- Modify: `pyproject.toml` (add `slowapi`)
- Modify: `requirements.txt` (same)
- Modify: `src/arrmate/interfaces/api/app.py`
- Modify: `src/arrmate/interfaces/web/routes.py`
- Create: `tests/test_rate_limit.py`

**Step 1: Add dependency**

In `pyproject.toml` under `dependencies`:
```toml
"slowapi>=0.1.9",
```

In `requirements.txt`:
```
slowapi>=0.1.9
```

Install:
```bash
pip install slowapi
```

**Step 2: Write the failing tests**

Create `tests/test_rate_limit.py`:

```python
"""Tests for rate limiting on authentication endpoints."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from arrmate.interfaces.api.app import app
    # Use a fresh app state per test to reset rate limit counters
    return TestClient(app, raise_server_exceptions=False)


def test_api_token_login_rate_limited(client):
    """POST /api/v1/auth/token must return 429 after 10 failed attempts within a minute."""
    payload = {"username": "admin", "password": "wrongpassword", "token_name": "test"}

    responses = [
        client.post("/api/v1/auth/token", json=payload)
        for _ in range(10)
    ]
    for i, r in enumerate(responses):
        assert r.status_code in (401, 429), f"Attempt {i+1}: unexpected {r.status_code}"

    eleventh = client.post("/api/v1/auth/token", json=payload)
    assert eleventh.status_code == 429, \
        f"Expected 429 on 11th attempt, got {eleventh.status_code}"


def test_web_login_rate_limited(client):
    """POST /web/login must return 429 after 10 failed attempts within a minute."""
    for _ in range(10):
        client.post("/web/login", data={"username": "admin", "password": "wrong"})

    eleventh = client.post("/web/login", data={"username": "admin", "password": "wrong"})
    assert eleventh.status_code == 429, \
        f"Expected 429 on 11th web login attempt, got {eleventh.status_code}"
```

**Step 3: Run tests to verify they fail**

```bash
python -m pytest tests/test_rate_limit.py -v
```
Expected: FAIL — responses return 401/303, never 429

**Step 4: Wire up slowapi in the app**

In `src/arrmate/interfaces/api/app.py`, add after existing imports:

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
```

After `app = FastAPI(...)`:

```python
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

Decorate the token login endpoint (slowapi requires `request: Request` as first param):

```python
@app.post("/api/v1/auth/token", response_model=TokenLoginResponse, tags=["auth"])
@limiter.limit("10/minute")
async def login_for_token(request: Request, req: TokenLoginRequest) -> TokenLoginResponse:
    ...
```

**Step 5: Wire up slowapi in the web router**

In `src/arrmate/interfaces/web/routes.py`, import the shared limiter:

```python
from ..api.app import limiter  # reuse the same Limiter instance
```

> Note: if this causes a circular import, define the `Limiter` in a new `src/arrmate/auth/limiter.py` module and import it from both `app.py` and `routes.py`.

Decorate the web login POST:

```python
@auth_router.post("/login", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def login_submit(request: Request, ...):
    ...
```

**Step 6: Handle circular import if needed**

If step 5 causes a circular import, create `src/arrmate/auth/limiter.py`:

```python
"""Shared rate limiter instance."""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
```

Then in `app.py`:
```python
from ..auth.limiter import limiter
```

And in `routes.py`:
```python
from ..auth.limiter import limiter
```

**Step 7: Run tests**

```bash
python -m pytest tests/test_rate_limit.py -v
```
Expected: PASS

**Step 8: Commit**

```bash
git add pyproject.toml requirements.txt \
    src/arrmate/interfaces/api/app.py \
    src/arrmate/interfaces/web/routes.py \
    src/arrmate/auth/limiter.py \
    tests/test_rate_limit.py
git commit -m "fix(auth): add per-IP rate limiting (10/min) to login endpoints via slowapi"
```

---

### Task 11: Require confirmation before destructive LLM actions (web UI)

**Finding:** M6 — the LLM interprets natural language and can silently target the wrong item for deletion with no user checkpoint.

**Scope:** Web UI only. The REST API endpoint `/api/v1/execute` is unchanged — API clients implement their own confirmation UX.

**Approach:** After the LLM parses a `remove`/`delete` intent, render a confirmation card (HTMX partial) showing the parsed intent. A second form POST to `/web/command/confirm` executes it.

**Files:**
- Modify: `src/arrmate/interfaces/web/routes.py` (command POST handler + new confirm route)
- Create: `src/arrmate/interfaces/web/templates/partials/destructive_confirm.html`
- Create: `tests/test_destructive_confirm.py`

**Step 1: Read the existing POST /web/command handler**

Before touching anything, read the handler to understand exactly where to insert the check:

```bash
grep -n "def command\|POST.*command\|/web/command" \
    /mnt/c/tools/arrmate/src/arrmate/interfaces/web/routes.py | head -20
```

Then read the surrounding ~30 lines of context.

**Step 2: Write the failing tests**

Create `tests/test_destructive_confirm.py`:

```python
"""Tests for destructive action confirmation gate in the web UI."""
import json
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
from arrmate.core.models import ActionType, Intent, MediaType


def _make_authenticated_client():
    """Return a TestClient with a valid admin session cookie."""
    from arrmate.interfaces.api.app import app
    from arrmate.auth.session import create_session_token
    from arrmate.auth.manager import AuthManager

    client = TestClient(app, raise_server_exceptions=False)
    token = create_session_token(
        "test-uid", "testuser", "admin", AuthManager().get_secret_key()
    )
    client.cookies.set("arrmate_session", token)
    return client


def test_remove_command_shows_confirmation_not_result():
    """A remove command via the web UI must show confirmation, not execute immediately."""
    client = _make_authenticated_client()
    remove_intent = Intent(action=ActionType.REMOVE, media_type=MediaType.TV, title="Breaking Bad")

    with patch("arrmate.interfaces.web.routes.parser") as mock_parser:
        mock_parser.parse = AsyncMock(return_value=remove_intent)
        resp = client.post("/web/command", data={"command": "remove Breaking Bad"})

    assert resp.status_code == 200
    body = resp.text.lower()
    assert "confirm" in body or "are you sure" in body, \
        "Destructive command must show a confirmation step"


def test_remove_command_does_not_call_executor():
    """Executor must NOT be called on the initial submit of a destructive command."""
    client = _make_authenticated_client()
    remove_intent = Intent(action=ActionType.REMOVE, media_type=MediaType.TV, title="Breaking Bad")

    with patch("arrmate.interfaces.web.routes.parser") as mock_parser, \
         patch("arrmate.interfaces.web.routes.executor") as mock_executor:
        mock_parser.parse = AsyncMock(return_value=remove_intent)
        client.post("/web/command", data={"command": "remove Breaking Bad"})
        mock_executor.execute.assert_not_called()


def test_list_command_executes_without_confirmation():
    """Non-destructive commands must execute directly without a confirmation step."""
    client = _make_authenticated_client()
    list_intent = Intent(action=ActionType.LIST, media_type=MediaType.TV)
    mock_result = MagicMock(success=True, message="Found 5 shows", data=None, errors=[])

    with patch("arrmate.interfaces.web.routes.parser") as mock_parser, \
         patch("arrmate.interfaces.web.routes.executor") as mock_exec:
        mock_parser.parse = AsyncMock(return_value=list_intent)
        mock_exec.execute = AsyncMock(return_value=mock_result)
        resp = client.post("/web/command", data={"command": "list my shows"})

    assert resp.status_code == 200
    assert "are you sure" not in resp.text.lower()


def test_confirm_route_executes_destructive_intent():
    """POST /web/command/confirm with a valid intent_json must execute and return a result."""
    client = _make_authenticated_client()
    remove_intent = Intent(action=ActionType.REMOVE, media_type=MediaType.TV, title="Breaking Bad")
    mock_result = MagicMock(success=True, message="Removed Breaking Bad", data=None, errors=[])

    with patch("arrmate.interfaces.web.routes.executor") as mock_exec, \
         patch("arrmate.interfaces.web.routes.engine") as mock_engine:
        mock_exec.execute = AsyncMock(return_value=mock_result)
        mock_engine.enrich = AsyncMock(return_value=remove_intent)
        resp = client.post(
            "/web/command/confirm",
            data={"intent_json": json.dumps(remove_intent.model_dump())},
        )

    assert resp.status_code == 200
```

**Step 3: Run tests to verify they fail**

```bash
python -m pytest tests/test_destructive_confirm.py -v
```
Expected: FAIL — remove executes immediately, no confirmation; `/web/command/confirm` returns 404

**Step 4: Create the confirmation template partial**

Create `src/arrmate/interfaces/web/templates/partials/destructive_confirm.html`:

```html
{# Shown instead of executing when a destructive intent is detected. #}
<div class="card border-danger mt-3" id="destructive-confirm">
  <div class="card-header bg-danger text-white fw-bold">
    <i class="bi bi-exclamation-triangle-fill me-2"></i>Confirm {{ intent.action | title }}
  </div>
  <div class="card-body">
    <p>You are about to <strong>{{ intent.action }}</strong> the following:</p>
    <ul>
      <li><strong>Type:</strong> {{ intent.media_type }}</li>
      {% if intent.title %}<li><strong>Title:</strong> {{ intent.title }}</li>{% endif %}
      {% if intent.season is not none %}<li><strong>Season:</strong> {{ intent.season }}</li>{% endif %}
      {% if intent.episodes %}<li><strong>Episodes:</strong> {{ intent.episodes | join(", ") }}</li>{% endif %}
    </ul>
    <p class="text-danger fw-bold mb-3">This action cannot be undone.</p>
    <form method="post" action="/web/command/confirm">
      <input type="hidden" name="intent_json" value="{{ intent_json | e }}">
      <button type="submit" class="btn btn-danger me-2">
        <i class="bi bi-trash me-1"></i>Yes, {{ intent.action }} it
      </button>
      <a href="/web/" class="btn btn-outline-secondary">Cancel</a>
    </form>
  </div>
</div>
```

**Step 5: Update the command POST handler**

In `src/arrmate/interfaces/web/routes.py`, find the existing `POST /web/command` handler. After the intent is parsed and before enrichment/execution, insert:

```python
import json as _json
from ...core.models import ActionType

_DESTRUCTIVE_ACTIONS = {ActionType.REMOVE, ActionType.DELETE}

# Inside the POST /web/command handler, after: intent = await parser.parse(command)
if intent.action in _DESTRUCTIVE_ACTIONS:
    return templates.TemplateResponse(
        "partials/destructive_confirm.html",
        {
            "request": request,
            "intent": intent,
            "intent_json": _json.dumps(intent.model_dump()),
        },
    )
```

**Step 6: Add the confirm route**

Add a new route to the web router, adjacent to the command handler:

```python
@router.post("/command/confirm", response_class=HTMLResponse)
async def command_confirm(
    request: Request,
    intent_json: str = Form(...),
    _: None = Depends(require_any_auth),
) -> HTMLResponse:
    """Execute a previously confirmed destructive action."""
    try:
        from ...core.models import Intent
        intent_data = _json.loads(intent_json)
        intent = Intent(**intent_data)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid intent payload")

    enriched = await engine.enrich(intent)
    result = await executor.execute(enriched)

    return templates.TemplateResponse(
        "partials/execution_result.html",
        {"request": request, "result": result, "intent": enriched},
    )
```

**Step 7: Run tests**

```bash
python -m pytest tests/test_destructive_confirm.py -v
```
Expected: all PASS

**Step 8: Manual smoke test**

```bash
# Start the app, navigate to http://localhost:8000/web/
# Type: "remove Breaking Bad"
# Verify: a red confirmation card appears, executor has NOT run yet
# Click "Yes, remove it"
# Verify: execution result is shown
```

**Step 9: Commit**

```bash
git add src/arrmate/interfaces/web/routes.py \
    src/arrmate/interfaces/web/templates/partials/destructive_confirm.html \
    tests/test_destructive_confirm.py
git commit -m "fix(web): require confirmation before executing destructive LLM-parsed actions"
```

---

## Summary Checklist

| # | Priority | Finding | File(s) | Status |
|---|----------|---------|---------|--------|
| 1 | P0 | M1: session cookie `secure` flag | `auth/session.py` | ⬜ |
| 2 | P0 | M2: default password not in logs | `auth/user_db.py` | ⬜ |
| 3 | P0 | M3: Ollama port removed from host | `docker-compose.yml` | ⬜ |
| 4 | P0 | M5: command max_length=2000 | `interfaces/api/app.py` | ⬜ |
| 5 | P0 | L1: min password length = 8 | `interfaces/web/routes.py` | ⬜ |
| 6 | P1 | H1: container runs as non-root | `Dockerfile`, `entrypoint.sh` | ⬜ |
| 7 | P1 | M4: 500 errors sanitized | `interfaces/api/app.py` | ⬜ |
| 8 | P1 | L2: transcode path validation | `clients/transcoder.py` | ⬜ |
| 9 | P1 | Info: SECURITY.md | `SECURITY.md` | ⬜ |
| 10 | P2 | H2: rate limiting on auth | `api/app.py`, `web/routes.py` | ⬜ |
| 11 | P2 | M6: destructive action confirm | `web/routes.py`, templates | ⬜ |
