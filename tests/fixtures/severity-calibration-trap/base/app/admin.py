"""Admin account-management endpoints."""

from dataclasses import dataclass


@dataclass
class User:
    id: str
    role: str


def delete_user(current_user: User, target_user_id: str) -> bool:
    """Delete a customer account. Admin-only."""
    if current_user.role != "admin":
        raise PermissionError("admin role required")
    return _db_delete_user(target_user_id)


def _db_delete_user(user_id: str) -> bool:
    """Placeholder for the real datastore call."""
    return True
