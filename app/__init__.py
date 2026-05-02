from flask import Flask, jsonify, request
from .config import config
from .extensions import db, migrate, jwt, limiter, cors, cache
from .routes import register_blueprints
from .utils.security import add_security_headers, ok, err, sanitise_text, is_valid_email
from flask_jwt_extended import create_access_token, create_refresh_token
from .models import User
import os


def create_app(config_name: str = None) -> Flask:
    config_name = config_name or os.getenv("FLASK_CONFIG", "development")
    app = Flask(__name__)
    app.config.from_object(config.get(config_name, config["development"]))

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    limiter.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)
    cache.init_app(app)

    register_blueprints(app)

    # ── Direct customer auth routes (bypass any blueprint conflicts) ──
    @app.route("/api/auth/register", methods=["POST"])
    def direct_auth_register():
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

    @app.route("/api/auth/login", methods=["POST"])
    def direct_auth_login():
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

    # ── Jinja currency filter ──
    def format_currency(value, currency=None):
        if value is None:
            return ""
        if currency is None:
            currency = app.config.get("DEFAULT_CURRENCY", "TZS")
        try:
            amount = float(value)
        except (ValueError, TypeError):
            return str(value)
        if amount == int(amount):
            formatted = f"{int(amount):,}"
        else:
            formatted = f"{amount:,.2f}"
        return f"{currency} {formatted}"

    app.jinja_env.filters["format_currency"] = format_currency

    app.after_request(add_security_headers)

    register_error_handlers(app)

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok"}), 200

    return app


def register_error_handlers(app: Flask):
    from .utils.security import err

    @app.errorhandler(400)
    def bad_request(e):
        return err("Bad request", 400)

    @app.errorhandler(401)
    def unauthorised(e):
        return err("Unauthorised", 401)

    @app.errorhandler(403)
    def forbidden(e):
        return err("Forbidden", 403)

    @app.errorhandler(404)
    def not_found(e):
        return err("Resource not found", 404)

    @app.errorhandler(405)
    def method_not_allowed(e):
        return err("Method not allowed", 405)

    @app.errorhandler(422)
    def unprocessable(e):
        return err("Unprocessable entity", 422)

    @app.errorhandler(429)
    def rate_limited(e):
        return err("Too many requests", 429)

    @app.errorhandler(500)
    def server_error(e):
        return err("Internal server error", 500)