from .products import products_bp, cat_bp, brand_bp, col_bp, tag_bp
from .search import search_bp
from flask import Flask
from .cart import cart_bp
from .orders import orders_bp
from .payments import payments_bp
from .inventory import inventory_bp
from .search import search_bp
from .wishlist import wishlist_bp
from .cms import cms_bp
from .admin import admin_bp
from .admin_auth import admin_auth_bp
from .notification import notifications_bp

def register_blueprints(app: Flask):
    # Products & catalogue
    app.register_blueprint(products_bp, url_prefix="/api")
    app.register_blueprint(cat_bp, url_prefix="/api")
    app.register_blueprint(brand_bp, url_prefix="/api")
    app.register_blueprint(col_bp, url_prefix="/api")
    app.register_blueprint(tag_bp, url_prefix="/api")
    app.register_blueprint(notifications_bp, url_prefix="/api")


    app.register_blueprint(cart_bp, url_prefix="/api")
    app.register_blueprint(orders_bp, url_prefix="/api")
    app.register_blueprint(payments_bp, url_prefix="/api")
    app.register_blueprint(inventory_bp, url_prefix="/api")
    app.register_blueprint(search_bp, url_prefix="/api")
    app.register_blueprint(wishlist_bp, url_prefix="/api")
    app.register_blueprint(cms_bp, url_prefix="/api")
    app.register_blueprint(admin_auth_bp, url_prefix="/api")
    app.register_blueprint(admin_bp, url_prefix="/api")