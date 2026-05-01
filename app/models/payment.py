from app.extensions import db
from app.models.helpers import _uuid, _now

class Payment(db.Model):
    __tablename__ = "payments"

    STATUSES = ["pending", "successful", "failed", "cancelled", "refunded"]

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    order_id = db.Column(db.String(36), db.ForeignKey("orders.id"), nullable=False)
    payment_method = db.Column(db.String(30), default="tigo_money")
    gateway_reference = db.Column(db.String(200))
    transaction_id = db.Column(db.String(200))
    phone_number = db.Column(db.String(20))
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(3), default="TZS")
    status = db.Column(db.String(20), default="pending")
    gateway_response = db.Column(db.JSON)
    paid_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=_now)
    updated_at = db.Column(db.DateTime, default=_now, onupdate=_now)

    def to_dict(self):
        return {
            "id": self.id, "order_id": self.order_id,
            "payment_method": self.payment_method,
            "transaction_id": self.transaction_id,
            "phone_number": self.phone_number,
            "amount": float(self.amount), "currency": self.currency,
            "status": self.status,
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
            "created_at": self.created_at.isoformat(),
        }