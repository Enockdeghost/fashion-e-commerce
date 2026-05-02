from flask import Flask
from .analytics import analytics_bp
from .cart import cart_bp
from .wishlist import wishlist_bp
from .orders import orders_bp
from .payments import payments_bp
from .checkout import checkout_bp
from .inventory import inventory_bp
from .search import search_bp
from .cms import cms_bp
from .coupons import coupons_bp
from .media import media_bp
from .admin_auth import admin_auth_bp
from .admin import admin_bp
from .notification import notifications_bp
from .products import products_bp, cat_bp, brand_bp, col_bp, tag_bp
from .frontend import frontend_bp
from .auth import auth_bp

def register_blueprints(app: Flask):
    # Frontend pages (no prefix) – serves /login, /register, /, etc.
    app.register_blueprint(frontend_bp)

    # Admin auth – provides /api/login, /api/me, /api/refresh (admin only)
    app.register_blueprint(admin_auth_bp, url_prefix="/api")

    # Customer auth – provides /api/auth/login, /api/auth/register, /api/auth/me
    app.register_blueprint(auth_bp, url_prefix="/api")

    # Products & catalogue
    app.register_blueprint(products_bp, url_prefix="/api")
    app.register_blueprint(cat_bp, url_prefix="/api")
    app.register_blueprint(brand_bp, url_prefix="/api")
    app.register_blueprint(col_bp, url_prefix="/api")
    app.register_blueprint(tag_bp, url_prefix="/api")

    # Cart & Wishlist
    app.register_blueprint(cart_bp, url_prefix="/api")
    app.register_blueprint(wishlist_bp, url_prefix="/api")

    # Orders & Checkout
    app.register_blueprint(orders_bp, url_prefix="/api")
    app.register_blueprint(payments_bp, url_prefix="/api")
    app.register_blueprint(checkout_bp, url_prefix="/api")

    # Inventory
    app.register_blueprint(inventory_bp, url_prefix="/api")

    # Search
    app.register_blueprint(search_bp, url_prefix="/api")

    # CMS (public content)
    app.register_blueprint(cms_bp, url_prefix="/api")

    # Coupons
    app.register_blueprint(coupons_bp, url_prefix="/api")

    # Media uploads
    app.register_blueprint(media_bp, url_prefix="/api")

    # Admin management (dashboard, CRUD)
    app.register_blueprint(admin_bp, url_prefix="/api")
    app.register_blueprint(notifications_bp, url_prefix="/api")

    # Analytics
    app.register_blueprint(analytics_bp, url_prefix="/api")