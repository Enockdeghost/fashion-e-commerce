from flask import Flask, jsonify, request
from .config import config
from .extensions import db, migrate, jwt, limiter, cors, cache
from .routes import register_blueprints
from .utils.security import add_security_headers, ok, err, sanitise_text, sanitise_html, is_valid_email
from flask_jwt_extended import create_access_token, create_refresh_token
from .models import User
import os
import uuid
from werkzeug.utils import secure_filename
from slugify import slugify


def create_app(config_name: str = None) -> Flask:
    config_name = config_name or os.getenv("FLASK_CONFIG", "development")
    app = Flask(__name__)
    app.config.from_object(config.get(config_name, config["development"]))

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    limiter.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": "*", "allow_headers": ["Content-Type", "Authorization"]}}, supports_credentials=True)
    cache.init_app(app)

    register_blueprints(app)

    # ── Direct customer auth routes (bypass any blueprint conflicts) ──
    @app.route("/api/auth/register", methods=["POST", "OPTIONS"])
    def direct_auth_register():
        if request.method == "OPTIONS":
            return ok({})
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

    @app.route("/api/auth/login", methods=["POST", "OPTIONS"])
    def direct_auth_login():
        if request.method == "OPTIONS":
            return ok({})
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

    UPLOAD_PRODUCT_FOLDER = os.path.join(app.root_path, 'static', 'uploads', 'products')
    os.makedirs(UPLOAD_PRODUCT_FOLDER, exist_ok=True)

    @app.route('/api/products', methods=['POST', 'OPTIONS'])
    def direct_create_product():
        if request.method == 'OPTIONS':
            return ok({})

        # Authenticate admin
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return err("Unauthorised", 401)
        token = auth_header.split(' ')[1]
        from flask_jwt_extended import decode_token
        try:
            payload = decode_token(token)
            admin_id = payload['sub']
            from app.models import AdminUser
            admin = AdminUser.query.get(admin_id)
            if not admin or not admin.is_active:
                return err("Unauthorised", 401)
        except Exception:
            return err("Invalid token", 401)

        file = request.files.get('file') if request.files else None
        data = request.form if request.files else (request.get_json(force=True) or {})

        name = sanitise_text(data.get("name", ""))
        price = data.get("base_price")
        if not name or not price:
            return err("Name and base_price are required")

        primary_image = None
        if file and file.filename:
            ext = secure_filename(file.filename).rsplit('.', 1)[-1].lower()
            if ext not in ('jpg', 'jpeg', 'png', 'webp', 'gif'):
                return err("Invalid image type")
            save_name = f"{uuid.uuid4().hex}.{ext}"
            file.save(os.path.join(UPLOAD_PRODUCT_FOLDER, save_name))
            primary_image = f"/static/uploads/products/{save_name}"
        else:
            primary_image = sanitise_text(data.get("primary_image", ""))
            if primary_image and not primary_image.startswith("http"):
                primary_image = f"/static{primary_image}"

        from app.models import Product, ProductImage
        product = Product(
            name=name,
            slug=slugify(name),
            description=sanitise_html(data.get("description", "")),
            short_description=sanitise_text(data.get("short_description", "")),
            base_price=float(price),
            compare_price=float(data["compare_price"]) if data.get("compare_price") else None,
            cost_price=float(data["cost_price"]) if data.get("cost_price") else None,
            currency=data.get("currency", "TZS"),
            category_id=data.get("category_id"),
            brand_id=data.get("brand_id"),
            is_featured=bool(data.get("is_featured", False)),
            is_new_arrival=bool(data.get("is_new_arrival", False)),
            is_active=bool(data.get("is_active", True)),
        )

        base_slug = product.slug
        counter = 1
        while Product.query.filter_by(slug=product.slug).first():
            product.slug = f"{base_slug}-{counter}"
            counter += 1

        db.session.add(product)
        db.session.flush()

        if primary_image:
            img = ProductImage(
                product_id=product.id,
                url=primary_image,
                is_primary=True,
                alt_text=name,
                sort_order=0,
            )
            db.session.add(img)

        db.session.commit()
        return ok(product.to_dict(full=True), "Product created", 201)

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