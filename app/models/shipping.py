from app.extensions import db
from app.models.helpers import _uuid, _now

class ShippingZone(db.Model):
    __tablename__ = "shipping_zones"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    name = db.Column(db.String(120), nullable=False)
    countries = db.Column(db.JSON)
    cities = db.Column(db.JSON)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=_now)

    rates = db.relationship("ShippingRate", backref="zone", lazy="dynamic", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id, "name": self.name,
            "countries": self.countries, "cities": self.cities,
            "rates": [r.to_dict() for r in self.rates],
        }


class ShippingRate(db.Model):
    __tablename__ = "shipping_rates"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    zone_id = db.Column(db.String(36), db.ForeignKey("shipping_zones.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    rate = db.Column(db.Numeric(12, 2), nullable=False)
    min_days = db.Column(db.Integer, default=1)
    max_days = db.Column(db.Integer, default=7)
    min_weight = db.Column(db.Float, default=0)
    max_weight = db.Column(db.Float)
    free_shipping_threshold = db.Column(db.Numeric(12, 2))
    is_active = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "rate": float(self.rate),
            "min_days": self.min_days, "max_days": self.max_days,
            "free_shipping_threshold": float(self.free_shipping_threshold) if self.free_shipping_threshold else None,
        }