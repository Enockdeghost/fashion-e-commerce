from flask import Blueprint, request
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity,
)
from app.models import AdminUser
from app.extensions import db
from app.utils.security import ok, err, sanitise_text
from datetime import datetime, timezone

admin_auth_bp = Blueprint("admin_auth", __name__, url_prefix="/admin")


@admin_auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(force=True)
    email = sanitise_text(data.get("email", "")).lower().strip()
    password = data.get("password", "")

    if not email or not password:
        return err("Email and password are required")

    admin = AdminUser.query.filter_by(email=email).first()
    if not admin or not admin.check_password(password):
        return err("Invalid credentials", 401)

    if not admin.is_active:
        return err("Account deactivated", 403)

    admin.last_login = datetime.now(timezone.utc)
    db.session.commit()

    access_token = create_access_token(identity=admin.id)
    refresh_token = create_refresh_token(identity=admin.id)

    return ok({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "admin": admin.to_dict(),
    }, "Login successful")


@admin_auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    current_admin_id = get_jwt_identity()
    new_access_token = create_access_token(identity=current_admin_id)
    return ok({"access_token": new_access_token}, "Token refreshed")


@admin_auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    admin_id = get_jwt_identity()
    admin = AdminUser.query.get(admin_id)
    if not admin or not admin.is_active:
        return err("Unauthorised", 401)
    return ok({"admin": admin.to_dict()})