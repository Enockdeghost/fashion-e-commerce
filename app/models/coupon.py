from app.extensions import db
from app.models.helpers import _uuid, _now
from datetime import timezone

class Coupon(db.Model):
    __tablename__ = "coupons"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    code = db.Column(db.String(30), nullable=False, unique=True)
    description = db.Column(db.String(255))
    discount_type = db.Column(db.String(20), nullable=False)
    discount_value = db.Column(db.Numeric(12, 2), nullable=False)
    minimum_purchase = db.Column(db.Numeric(12, 2), default=0)
    maximum_discount = db.Column(db.Numeric(12, 2))
    usage_limit = db.Column(db.Integer)
    used_count = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    starts_at = db.Column(db.DateTime, nullable=False, default=_now)
    expires_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=_now)

    def is_valid(self, subtotal):
        now = _now()
        if not self.is_active:
            return False, "Coupon is inactive"
        if self.starts_at and now < self.starts_at.replace(tzinfo=timezone.utc):
            return False, "Coupon not yet valid"
        if self.expires_at and now > self.expires_at.replace(tzinfo=timezone.utc):
            return False, "Coupon has expired"
        if self.usage_limit and self.used_count >= self.usage_limit:
            return False, "Coupon usage limit reached"
        if subtotal < float(self.minimum_purchase):
            return False, f"Minimum purchase of {self.minimum_purchase} required"
        return True, "Valid"

    def calculate_discount(self, subtotal):
        if self.discount_type == "percentage":
            discount = subtotal * (float(self.discount_value) / 100)
            if self.maximum_discount:
                discount = min(discount, float(self.maximum_discount))
        else:
            discount = min(float(self.discount_value), subtotal)
        return round(discount, 2)

    def to_dict(self):
        return {
            "id": self.id, "code": self.code, "description": self.description,
            "discount_type": self.discount_type,
            "discount_value": float(self.discount_value),
            "minimum_purchase": float(self.minimum_purchase),
            "usage_limit": self.usage_limit, "used_count": self.used_count,
            "is_active": self.is_active,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }