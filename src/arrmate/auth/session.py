"""Session token management via signed cookies."""

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from fastapi.responses import Response

SESSION_COOKIE = "arrmate_session"
SESSION_MAX_AGE = 86400  # 24 hours


def create_session_token(
    user_id: str,
    username: str,
    role: str,
    secret_key: str,
) -> str:
    """Create a signed session token with full user info."""
    s = URLSafeTimedSerializer(secret_key)
    return s.dumps({"user_id": user_id, "username": username, "role": role})


def validate_session_token(token: str, secret_key: str) -> dict | None:
    """Validate session token. Returns dict with user_id/username/role or None.

    Handles legacy format {"user": "username"} by treating as admin.
    """
    s = URLSafeTimedSerializer(secret_key)
    try:
        data = s.loads(token, max_age=SESSION_MAX_AGE)
        # Legacy migration: old tokens only had {"user": "username"}
        if "user" in data and "user_id" not in data:
            return {
                "user_id": "legacy",
                "username": data["user"],
                "role": "admin",
            }
        if "user_id" in data and "username" in data and "role" in data:
            return data
        return None
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
        secure=True,
    )


def clear_session_cookie(response: Response) -> None:
    """Delete the session cookie."""
    response.delete_cookie(SESSION_COOKIE, samesite="lax")
