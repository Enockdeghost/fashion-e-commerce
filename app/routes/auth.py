from flask import Blueprint, request
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
from app.models import User
from app.extensions import db
from app.utils.security import ok, err, sanitise_text, is_valid_email

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")  

@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(force=True)
    email = sanitise_text(data.get("email", "")).lower().strip()
    password = data.get("password", "")
    first_name = sanitise_text(data.get("first_name", ""))
    last_name = sanitise_text(data.get("last_name", ""))

    if not email or not password:
        return err("Email and password are required")
    if not is_valid_email(email):
        return err("Invalid email address")
    if User.query.filter_by(email=email).first():
        return err("An account with that email already exists")

    user = User(email=email, first_name=first_name, last_name=last_name)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    access_token = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)
    return ok({"user": user.to_dict(), "access_token": access_token, "refresh_token": refresh_token}, "Account created", 201)

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(force=True)
    email = sanitise_text(data.get("email", "")).lower().strip()
    password = data.get("password", "")

    if not email or not password:
        return err("Email and password are required")

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return err("Invalid credentials", 401)

    if not user.is_active:
        return err("Account is deactivated", 403)

    access_token = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)
    return ok({"user": user.to_dict(), "access_token": access_token, "refresh_token": refresh_token}, "Login successful")

@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user or not user.is_active:
        return err("User not found", 404)
    return ok({"user": user.to_dict()})