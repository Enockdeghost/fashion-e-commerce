from app.extensions import db
from app.models.helpers import _uuid, _now

class Cart(db.Model):
    __tablename__ = "carts"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    session_token = db.Column(db.String(128), unique=True, nullable=False, index=True)
    coupon_id = db.Column(db.String(36), db.ForeignKey("coupons.id"), nullable=True)
    currency = db.Column(db.String(3), default="TZS")
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=_now)
    updated_at = db.Column(db.DateTime, default=_now, onupdate=_now)

    items = db.relationship("CartItem", backref="cart", lazy="dynamic", cascade="all, delete-orphan")
    coupon = db.relationship("Coupon", foreign_keys=[coupon_id])

    @property
    def subtotal(self):
        return sum(item.line_total for item in self.items)

    @property
    def is_expired(self):
        from datetime import timezone
        return _now() > self.expires_at.replace(tzinfo=timezone.utc)

    def to_dict(self):
        return {
            "id": self.id, "session_token": self.session_token,
            "items": [i.to_dict() for i in self.items],
            "subtotal": float(self.subtotal),
            "coupon": self.coupon.to_dict() if self.coupon else None,
            "expires_at": self.expires_at.isoformat(),
        }


class CartItem(db.Model):
    __tablename__ = "cart_items"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    cart_id = db.Column(db.String(36), db.ForeignKey("carts.id"), nullable=False)
    product_id = db.Column(db.String(36), db.ForeignKey("products.id"), nullable=False)
    variant_id = db.Column(db.String(36), db.ForeignKey("product_variants.id"), nullable=True)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Numeric(12, 2), nullable=False)
    created_at = db.Column(db.DateTime, default=_now)

    product = db.relationship("Product")
    variant = db.relationship("ProductVariant")

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    def to_dict(self):
        return {
            "id": self.id, "product": self.product.to_dict(),
            "variant": self.variant.to_dict() if self.variant else None,
            "quantity": self.quantity,
            "unit_price": float(self.unit_price),
            "line_total": float(self.line_total),
        }