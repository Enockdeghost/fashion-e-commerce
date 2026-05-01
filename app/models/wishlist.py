from app.extensions import db
from app.models.helpers import _uuid, _now

class Wishlist(db.Model):
    __tablename__ = "wishlists"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    session_token = db.Column(db.String(128), nullable=False, index=True)
    product_id = db.Column(db.String(36), db.ForeignKey("products.id"), nullable=False)
    variant_id = db.Column(db.String(36), db.ForeignKey("product_variants.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=_now)

    product = db.relationship("Product")
    variant = db.relationship("ProductVariant")

    __table_args__ = (
        db.UniqueConstraint("session_token", "product_id", "variant_id", name="uq_wishlist"),
    )

    def to_dict(self):
        return {
            "id": self.id, "product": self.product.to_dict(),
            "variant": self.variant.to_dict() if self.variant else None,
            "created_at": self.created_at.isoformat(),
        }