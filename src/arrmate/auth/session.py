"""Session token management via signed cookies."""

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from fastapi.responses import Response

SESSION_COOKIE = "arrmate_session"
SESSION_MAX_AGE = 86400  # 24 hours


def create_session_token(username: str, secret_key: str) -> str:
    """Create a signed session token."""
    s = URLSafeTimedSerializer(secret_key)
    return s.dumps({"user": username})


def validate_session_token(token: str, secret_key: str) -> str | None:
    """Validate a session token and return the username, or None."""
    s = URLSafeTimedSerializer(secret_key)
    try:
        data = s.loads(token, max_age=SESSION_MAX_AGE)
        return data.get("user")
    except (BadSignature, SignatureExpired):
        return None


def set_session_cookie(response: Response, token: str) -> None:
    """Set the session cookie on a response."""
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
    )


def clear_session_cookie(response: Response) -> None:
    """Delete the session cookie."""
    response.delete_cookie(SESSION_COOKIE, samesite="lax")
