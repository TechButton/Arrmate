"""Authentication package for Arrmate."""

from .manager import AuthManager

auth_manager = AuthManager()

__all__ = ["auth_manager", "AuthManager"]
