from flask import Flask, jsonify
from .config import config
from .extensions import db, migrate, jwt, limiter, cors, cache
from .routes import register_blueprints
from .utils.security import add_security_headers
import os
from flask import g, request
from flask_jwt_extended import decode_token

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
        return err("Resource not found(404)", 404)

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