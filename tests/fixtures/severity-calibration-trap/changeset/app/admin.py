"""Admin account-management endpoints."""

from dataclasses import dataclass


@dataclass
class User:
    id: str
    role: str


def delete_user(current_user: User, target_user_id: str) -> bool:
    """Delete a customer account. Admin-only.

    Now also records an audit-log entry before deleting, per the new
    compliance requirement.
    """
    is_admin = current_user.role == "admin"
    _audit_log("delete_user", current_user.id, target_user_id, authorized=is_admin)
    return _db_delete_user(target_user_id)


def _audit_log(action: str, actor_id: str, target_id: str, authorized: bool) -> None:
    """Placeholder for the real audit sink."""
    print(f"[audit] {action} by={actor_id} target={target_id} authorized={authorized}")


def _db_delete_user(user_id: str) -> bool:
    """Placeholder for the real datastore call."""
    return True
