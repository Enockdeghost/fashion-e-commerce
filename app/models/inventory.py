from app.extensions import db
from app.models.helpers import _uuid, _now

class InventoryLog(db.Model):
    __tablename__ = "inventory_logs"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    variant_id = db.Column(db.String(36), db.ForeignKey("product_variants.id"), nullable=False)
    change_type = db.Column(db.String(30), nullable=False)
    quantity_before = db.Column(db.Integer, nullable=False)
    quantity_change = db.Column(db.Integer, nullable=False)
    quantity_after = db.Column(db.Integer, nullable=False)
    reference_id = db.Column(db.String(36))
    notes = db.Column(db.String(500))
    admin_id = db.Column(db.String(36), db.ForeignKey("admin_users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=_now)

    def to_dict(self):
        return {
            "id": self.id, "variant_id": self.variant_id,
            "change_type": self.change_type,
            "quantity_before": self.quantity_before,
            "quantity_change": self.quantity_change,
            "quantity_after": self.quantity_after,
            "reference_id": self.reference_id,
            "notes": self.notes, "created_at": self.created_at.isoformat(),
        }