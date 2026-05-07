from flask import Flask, jsonify, request, make_response
from .config import config
from .extensions import db, migrate, jwt, limiter, cors, cache
from .routes import register_blueprints
from .utils.security import add_security_headers, ok, err, sanitise_text, sanitise_html, is_valid_email
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
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

    # ── JWT cookie configuration ─────────────────────────────
    app.config["JWT_ACCESS_COOKIE_NAME"] = "admin_token"
    app.config["JWT_COOKIE_CSRF_PROTECT"] = False

    limiter.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": "*", "allow_headers": ["Content-Type", "Authorization"]}}, supports_credentials=True)
    cache.init_app(app)

    @app.route('/api/categories', methods=['GET'])
    def direct_list_categories():
        from app.models import Category
        cats = Category.query.filter_by(is_active=True, parent_id=None).all()
        return ok([c.to_dict() for c in cats])

    @app.route('/api/brands', methods=['GET'])
    def direct_list_brands():
        from app.models import Brand
        brands = Brand.query.filter_by(is_active=True).all()
        return ok([b.to_dict() for b in brands])

    @app.route('/api/products', methods=['GET'])
    def direct_list_products():
        from app.models import Product, Category, Brand
        from app.utils.security import validate_pagination
        from sqlalchemy import or_
        page, per_page = validate_pagination(request.args)
        q = Product.query.filter_by(is_deleted=False, is_active=True)

        if cat := request.args.get("category"):
            q = q.join(Category).filter(or_(Category.id == cat, Category.slug == cat))
        if brand := request.args.get("brand"):
            q = q.join(Brand).filter(or_(Brand.id == brand, Brand.slug == brand))
        if search := request.args.get("q"):
            like = f"%{search}%"
            q = q.filter(or_(Product.name.ilike(like), Product.description.ilike(like)))

        sort_key = request.args.get("sort", "newest")
        sort_map = {
            "newest": Product.created_at.desc(),
            "price_asc": Product.base_price.asc(),
            "price_desc": Product.base_price.desc(),
        }
        q = q.order_by(sort_map.get(sort_key, Product.created_at.desc()))

        paginated = q.paginate(page=page, per_page=per_page, error_out=False)
        return ok({
            "products": [p.to_dict() for p in paginated.items],
            "pagination": {
                "page": page, "per_page": per_page,
                "total": paginated.total, "pages": paginated.pages,
            },
        })

    @app.route('/api/blog', methods=['GET'])
    def direct_list_blog_posts():
        from app.models import BlogPost
        posts = BlogPost.query.order_by(BlogPost.created_at.desc()).all()
        return ok({"blog_posts": [p.to_dict(full=True) for p in posts]})

    @app.route('/api/blog/<post_id>', methods=['GET'])
    def direct_get_blog_post(post_id):
        from app.models import BlogPost
        post = BlogPost.query.get_or_404(post_id)
        return ok(post.to_dict(full=True))

    @app.route('/api/blog/<post_id>', methods=['DELETE'])
    @jwt_required()
    def direct_delete_blog_post(post_id):
        from app.models import BlogPost, AdminUser
        admin_id = get_jwt_identity()
        admin = AdminUser.query.get(admin_id)
        if not admin or not admin.is_active:
            return err("Unauthorised", 401)
        post = BlogPost.query.get_or_404(post_id)
        db.session.delete(post)
        db.session.commit()
        return ok(message="Blog post deleted")

    BLOG_UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads', 'blog')
    os.makedirs(BLOG_UPLOAD_FOLDER, exist_ok=True)

    @app.route('/api/blog', methods=['POST'])
    @jwt_required()
    def direct_create_blog_post():
        from app.models import BlogPost, AdminUser
        admin_id = get_jwt_identity()
        admin = AdminUser.query.get(admin_id)
        if not admin or not admin.is_active:
            return err("Unauthorised", 401)

        file = request.files.get('file') if request.files else None
        data = request.form if request.files else (request.get_json(force=True) or {})

        title = sanitise_text(data.get("title", ""))
        if not title:
            return err("Title is required")

        cover_url = None
        if file and file.filename:
            ext = secure_filename(file.filename).rsplit('.', 1)[-1].lower()
            if ext not in ('jpg', 'jpeg', 'png', 'webp', 'gif'):
                return err("Invalid image type")
            save_name = f"{uuid.uuid4().hex}.{ext}"
            file.save(os.path.join(BLOG_UPLOAD_FOLDER, save_name))
            cover_url = f"/static/uploads/blog/{save_name}"
        else:
            cover_url = sanitise_text(data.get("cover_image_url", ""))

        post = BlogPost(
            title=title,
            slug=slugify(title),
            excerpt=sanitise_text(data.get("excerpt", "")),
            content=sanitise_html(data.get("content", "")),
            cover_image_url=cover_url,
            author_id=admin.id,
            is_published=str(data.get("is_published", "false")).lower() == "true",
            meta_title=sanitise_text(data.get("meta_title", "")),
            meta_description=sanitise_text(data.get("meta_description", "")),
        )
        if post.is_published:
            from datetime import datetime, timezone
            post.published_at = datetime.now(timezone.utc)
        db.session.add(post)
        db.session.commit()
        return ok(post.to_dict(full=True), "Blog post created", 201)

    @app.route('/blog/<slug>')
    def direct_blog_post(slug):
        from app.models import BlogPost
        post = BlogPost.query.filter_by(slug=slug).first_or_404()
        from flask import render_template
        from datetime import datetime, timezone
        return render_template('blog/post.html', post=post, now=datetime.now(timezone.utc))

    @app.route('/lookbook/<category>')
    def direct_lookbook_category(category):
        from app.models import Category, Product
        cat = Category.query.filter(
            (Category.slug == category) | (Category.id == category)
        ).first_or_404()
        products = Product.query.filter_by(
            category_id=cat.id, is_active=True, is_deleted=False
        ).order_by(Product.created_at.desc()).limit(24).all()
        from flask import render_template
        from datetime import datetime, timezone
        return render_template('lookbook/category.html',
                               category=cat,
                               products=products,
                               now=datetime.now(timezone.utc))

    register_blueprints(app)

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

    # ── Product creation (admin protected) ──
    UPLOAD_PRODUCT_FOLDER = os.path.join(app.root_path, 'static', 'uploads', 'products')
    os.makedirs(UPLOAD_PRODUCT_FOLDER, exist_ok=True)

    @app.route('/api/products', methods=['POST'])
    @jwt_required()
    def direct_create_product():
        from app.models import AdminUser, Product, ProductImage
        admin_id = get_jwt_identity()
        admin = AdminUser.query.get(admin_id)
        if not admin or not admin.is_active:
            return err("Unauthorised", 401)

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

    # ── Cart routes (no auth required) ──
    @app.route('/api/cart', methods=['GET'])
    @app.route('/api/cart/', methods=['GET'])
    def direct_get_cart():
        token = request.headers.get('X-Cart-Token')
        if not token:
            return ok({"cart": None})
        from app.models import Cart
        cart = Cart.query.filter_by(session_token=token).first()
        if not cart:
            return ok({"cart": None})
        return ok({"cart": cart.to_dict(), "token": token})

    @app.route('/api/cart/add', methods=['POST'])
    def direct_cart_add():
        data = request.get_json(force=True)
        token = data.get('token') or request.headers.get('X-Cart-Token')
        if not token:
            return err("Cart token required")
        product_id = data.get('product_id')
        variant_id = data.get('variant_id')
        quantity = int(data.get('quantity', 1))

        from app.models import Product, ProductVariant, Cart, CartItem
        product = Product.query.get(product_id)
        if not product:
            return err("Product not found")

        variant = None
        if variant_id:
            variant = ProductVariant.query.get(variant_id)

        cart = Cart.query.filter_by(session_token=token).first()
        if not cart:
            from datetime import datetime, timezone, timedelta
            expiry = datetime.now(timezone.utc) + timedelta(hours=72)
            cart = Cart(session_token=token, expires_at=expiry)
            db.session.add(cart)
            db.session.flush()

        existing = CartItem.query.filter_by(cart_id=cart.id, product_id=product.id, variant_id=variant_id).first()
        if existing:
            existing.quantity += quantity
        else:
            price = float(variant.price) if variant and variant.price else float(product.base_price)
            item = CartItem(cart_id=cart.id, product_id=product.id, variant_id=variant_id,
                            quantity=quantity, unit_price=price)
            db.session.add(item)
        db.session.commit()
        return ok({"cart": cart.to_dict(), "token": token}, "Item added")

    @app.route('/api/cart/remove/<item_id>/', methods=['DELETE'])
    @app.route('/api/cart/remove/<item_id>', methods=['DELETE'])
    def direct_cart_remove(item_id):
        from app.models import CartItem, Cart
        item = CartItem.query.get(item_id)
        if item:
            cart_id = item.cart_id
            db.session.delete(item)
            db.session.commit()
            cart = Cart.query.get(cart_id)
            return ok({"cart": cart.to_dict() if cart else None})
        return err("Item not found", 404)

    # ── Wishlist routes (no auth required) ──
    @app.route('/api/wishlist', methods=['GET'])
    def direct_get_wishlist():
        token = request.headers.get('X-Cart-Token')
        if not token:
            return ok({"wishlist": []})
        from app.models import Wishlist
        items = Wishlist.query.filter_by(session_token=token).order_by(Wishlist.created_at.desc()).all()
        return ok({"wishlist": [i.to_dict() for i in items], "token": token})

    @app.route('/api/wishlist', methods=['POST'])
    def direct_wishlist_add():
        data = request.get_json(force=True)
        token = data.get('token') or request.headers.get('X-Cart-Token')
        if not token:
            return err("Wishlist token required")
        product_id = data.get('product_id')
        variant_id = data.get('variant_id')
        if not product_id:
            return err("product_id is required")
        from app.models import Wishlist, Product
        product = Product.query.get(product_id)
        if not product:
            return err("Product not found")
        exists = Wishlist.query.filter_by(session_token=token, product_id=product_id, variant_id=variant_id).first()
        if exists:
            return ok({"wishlist": exists.to_dict(), "token": token}, "Already in wishlist")
        entry = Wishlist(session_token=token, product_id=product_id, variant_id=variant_id)
        db.session.add(entry)
        db.session.commit()
        return ok({"wishlist": entry.to_dict(), "token": token}, "Added to wishlist")

    @app.route('/api/wishlist/<item_id>', methods=['DELETE'])
    @app.route('/api/wishlist/<item_id>/', methods=['DELETE'])
    def direct_wishlist_remove(item_id):
        from app.models import Wishlist
        entry = Wishlist.query.get(item_id)
        if not entry:
            return err("Wishlist item not found", 404)
        db.session.delete(entry)
        db.session.commit()
        return ok({}, "Removed from wishlist")

    # ── Banner creation (admin protected) ──
    BANNER_UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads', 'banners')
    os.makedirs(BANNER_UPLOAD_FOLDER, exist_ok=True)

    @app.route('/api/banners', methods=['POST'])
    @jwt_required()
    def direct_create_banner():
        from app.models import AdminUser, Banner
        admin_id = get_jwt_identity()
        admin = AdminUser.query.get(admin_id)
        if not admin or not admin.is_active:
            return err("Unauthorised", 401)

        file = request.files.get('file') if request.files else None
        data = request.form if request.files else (request.get_json(force=True) or {})

        image_url = None
        if file and file.filename:
            ext = secure_filename(file.filename).rsplit('.', 1)[-1].lower()
            if ext not in ('jpg', 'jpeg', 'png', 'webp', 'gif'):
                return err("Invalid image type")
            save_name = f"{uuid.uuid4().hex}.{ext}"
            file.save(os.path.join(BANNER_UPLOAD_FOLDER, save_name))
            image_url = f"/static/uploads/banners/{save_name}"
        else:
            image_url = sanitise_text(data.get("image_url", ""))
            if not image_url:
                return err("image_url or file upload is required")

        banner = Banner(
            title=sanitise_text(data.get("title", "")),
            subtitle=sanitise_text(data.get("subtitle", "")),
            image_url=image_url,
            link_url=sanitise_text(data.get("link_url", "")),
            position=data.get("position", "homepage_hero"),
            is_active=str(data.get("is_active", "true")).lower() != "false",
        )
        db.session.add(banner)
        db.session.commit()
        return ok(banner.to_dict(), "Banner created", 201)

    # ── Admin login (sets HttpOnly cookie) ──
    @app.route("/api/admin/login", methods=["POST"])
    def direct_admin_login():
        data = request.get_json(force=True)
        email = sanitise_text(data.get("email", "")).lower().strip()
        password = data.get("password", "")

        from app.models import AdminUser
        admin = AdminUser.query.filter_by(email=email).first()
        if not admin or not admin.check_password(password):
            return err("Invalid credentials", 401)
        if not admin.is_active:
            return err("Account deactivated", 403)

        access_token = create_access_token(identity=admin.id)
        resp = make_response(ok({"access_token": access_token, "admin": admin.to_dict()}, "Login successful"))
        resp.set_cookie(
            "admin_token",
            access_token,
            httponly=True,
            secure=False,
            samesite="Lax",
            max_age=3600,
            path="/"
        )
        return resp

    @app.route("/api/admin/logout", methods=["POST"])
    def direct_admin_logout():
        resp = make_response(ok(message="Logged out"))
        resp.set_cookie("admin_token", "", expires=0, path="/")
        return resp

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