from .admin_user import AdminUser
from .analytics import AbandonedCart
from .brand import Brand
from .cart import Cart, CartItem
from .category import Category
from .cms import Banner, BlogPost, Page, FAQ
from .coupon import Coupon
from .helpers import _uuid, _now, _gen_order_number, _gen_sku
from .inventory import InventoryLog
from .media import Media
from .order import Order, OrderItem, OrderStatusHistory
from .payment import Payment
from .product import Product, ProductVariant, ProductImage, ProductVideo
from .shipping import ShippingZone, ShippingRate
from .tag import Tag
from .wishlist import Wishlist
from .user import User

# Define Collection if it doesn't exist as a separate model
# It might be used in product associations
from app.models.associations import product_collections
from sqlalchemy import Table, Column, String, DateTime
from app.extensions import db

# Create a simple Collection model if not defined
class Collection(db.Model):
    __tablename__ = 'collections'
    
    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    name = db.Column(db.String(120), nullable=False, unique=True)
    slug = db.Column(db.String(140), unique=True, nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=_now)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'slug': self.slug,
            'description': self.description,
            'is_active': self.is_active
        }

__all__ = [
    'AdminUser',
    'AbandonedCart',
    'Banner',
    'BlogPost',
    'Brand',
    'Cart',
    'CartItem',
    'Category',
    'Collection',
    'Coupon',
    'FAQ',
    'InventoryLog',
    'Media',
    'Order',
    'OrderItem',
    'OrderStatusHistory',
    'Page',
    'Payment',
    'Product',
    'ProductImage',
    'ProductVariant',
    'ProductVideo',
    'ShippingZone',
    'ShippingRate',
    'Tag',
    'Wishlist',
    '_uuid',
    '_now',
    '_gen_order_number',
    '_gen_sku'
]
