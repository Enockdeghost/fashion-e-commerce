from app.extensions import db
from app.models.helpers import _uuid, _now

class TransportOption(db.Model):
    __tablename__ = "transport_options"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    name = db.Column(db.String(150), nullable=False)
    cost = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    city = db.Column(db.String(150))                # optional – if set, only shown for this city
    estimated_days = db.Column(db.String(50))       # e.g. "2-3 days"
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=_now)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "cost": float(self.cost),
            "city": self.city,
            "estimated_days": self.estimated_days,
            "is_active": self.is_active
        }