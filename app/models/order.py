from app.extensions import db
from app.models.helpers import _uuid, _now, _gen_order_number

class Order(db.Model):
    __tablename__ = "orders"

    ORDER_STATUSES = [
        "pending", "paid", "processing", "shipped",
        "delivered", "cancelled", "refunded", "return_requested"
    ]

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    order_number = db.Column(db.String(30), unique=True, nullable=False, default=_gen_order_number)
    session_token = db.Column(db.String(128), index=True)

    status = db.Column(db.String(30), nullable=False, default="pending")

    customer_email = db.Column(db.String(200), nullable=False)
    customer_phone = db.Column(db.String(30))
    customer_name = db.Column(db.String(200))

    shipping_name = db.Column(db.String(200))
    shipping_phone = db.Column(db.String(30))
    shipping_street = db.Column(db.String(300))
    shipping_city = db.Column(db.String(120))
    shipping_region = db.Column(db.String(120))
    shipping_country = db.Column(db.String(3), default="TZ")
    shipping_postal_code = db.Column(db.String(20))

    currency = db.Column(db.String(3), default="TZS")
    subtotal = db.Column(db.Numeric(12, 2), nullable=False)
    discount_amount = db.Column(db.Numeric(12, 2), default=0)
    shipping_amount = db.Column(db.Numeric(12, 2), default=0)
    tax_amount = db.Column(db.Numeric(12, 2), default=0)
    total = db.Column(db.Numeric(12, 2), nullable=False)

    coupon_id = db.Column(db.String(36), db.ForeignKey("coupons.id"), nullable=True)
    coupon_code = db.Column(db.String(30))

    shipping_zone_id = db.Column(db.String(36), db.ForeignKey("shipping_zones.id"), nullable=True)
    shipping_rate_id = db.Column(db.String(36), db.ForeignKey("shipping_rates.id"), nullable=True)
    tracking_number = db.Column(db.String(120))
    courier = db.Column(db.String(80))
    estimated_delivery = db.Column(db.DateTime)

    customer_notes = db.Column(db.Text)
    admin_notes = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=_now)
    updated_at = db.Column(db.DateTime, default=_now, onupdate=_now)
    paid_at = db.Column(db.DateTime)
    shipped_at = db.Column(db.DateTime)
    delivered_at = db.Column(db.DateTime)
    cancelled_at = db.Column(db.DateTime)

    items = db.relationship("OrderItem", backref="order", lazy="dynamic", cascade="all, delete-orphan")
    payments = db.relationship("Payment", backref="order", lazy="dynamic")
    status_history = db.relationship("OrderStatusHistory", backref="order", lazy="dynamic")

    def to_dict(self, full=False):
        data = {
            "id": self.id, "order_number": self.order_number,
            "status": self.status,
            "customer_name": self.customer_name,
            "customer_email": self.customer_email,
            "total": float(self.total), "currency": self.currency,
            "created_at": self.created_at.isoformat(),
        }
        if full:
            data.update({
                "customer_phone": self.customer_phone,
                "shipping_address": {
                    "name": self.shipping_name, "phone": self.shipping_phone,
                    "street": self.shipping_street, "city": self.shipping_city,
                    "region": self.shipping_region, "country": self.shipping_country,
                    "postal_code": self.shipping_postal_code,
                },
                "subtotal": float(self.subtotal),
                "discount_amount": float(self.discount_amount),
                "shipping_amount": float(self.shipping_amount),
                "tax_amount": float(self.tax_amount),
                "coupon_code": self.coupon_code,
                "tracking_number": self.tracking_number,
                "courier": self.courier,
                "estimated_delivery": self.estimated_delivery.isoformat() if self.estimated_delivery else None,
                "customer_notes": self.customer_notes,
                "items": [i.to_dict() for i in self.items],
                "status_history": [h.to_dict() for h in self.status_history.order_by(OrderStatusHistory.created_at)],
            })
        return data


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    order_id = db.Column(db.String(36), db.ForeignKey("orders.id"), nullable=False)
    product_id = db.Column(db.String(36), db.ForeignKey("products.id"), nullable=False)
    variant_id = db.Column(db.String(36), db.ForeignKey("product_variants.id"), nullable=True)
    product_name = db.Column(db.String(255))
    variant_sku = db.Column(db.String(60))
    size = db.Column(db.String(20))
    color = db.Column(db.String(50))
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(12, 2), nullable=False)
    line_total = db.Column(db.Numeric(12, 2), nullable=False)
    image_url = db.Column(db.String(500))

    product = db.relationship("Product")
    variant = db.relationship("ProductVariant")

    def to_dict(self):
        return {
            "id": self.id, "product_name": self.product_name,
            "variant_sku": self.variant_sku, "size": self.size, "color": self.color,
            "quantity": self.quantity,
            "unit_price": float(self.unit_price),
            "line_total": float(self.line_total),
            "image_url": self.image_url,
        }


class OrderStatusHistory(db.Model):
    __tablename__ = "order_status_history"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    order_id = db.Column(db.String(36), db.ForeignKey("orders.id"), nullable=False)
    from_status = db.Column(db.String(30))
    to_status = db.Column(db.String(30), nullable=False)
    notes = db.Column(db.String(500))
    admin_id = db.Column(db.String(36), db.ForeignKey("admin_users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=_now)

    def to_dict(self):
        return {
            "from_status": self.from_status, "to_status": self.to_status,
            "notes": self.notes, "created_at": self.created_at.isoformat(),
        }