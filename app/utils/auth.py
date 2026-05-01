from flask_jwt_extended import get_jwt_identity

from flask import g
from app.models import AdminUser


def get_current_admin() -> AdminUser | None:
    """
    Return the AdminUser object for the currently authenticated admin.
    Must be called inside a route protected by @admin_required or @roles_required.
    Returns None if no admin is set (emergency fallback).
    """
    admin = getattr(g, "admin", None)
    if admin is None:
        try:
            admin_id = get_jwt_identity()
            if admin_id:
                admin = AdminUser.query.get(admin_id)
                if admin and admin.is_active:
                    g.admin = admin
        except Exception:
            pass
    return admin if admin and admin.is_active else None


def has_role(required_role: str) -> bool:
    """Check if the current admin has a specific role."""
    admin = get_current_admin()
    return admin is not None and admin.role == required_role