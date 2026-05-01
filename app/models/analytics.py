from app.extensions import db
from app.models.helpers import _uuid, _now

class AbandonedCart(db.Model):
    __tablename__ = "abandoned_carts"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    session_token = db.Column(db.String(128))
    items_snapshot = db.Column(db.JSON)
    subtotal = db.Column(db.Numeric(12, 2))
    email = db.Column(db.String(200))
    recovery_sent = db.Column(db.Boolean, default=False)
    recovered = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=_now)