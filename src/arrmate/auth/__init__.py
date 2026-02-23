"""Authentication package for Arrmate."""

from .manager import AuthManager
from . import user_db

auth_manager = AuthManager()

__all__ = ["auth_manager", "AuthManager", "user_db"]
