from slugify import slugify
from app.extensions import db
from app.models.helpers import _uuid, _now

class Brand(db.Model):
    __tablename__ = "brands"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    name = db.Column(db.String(120), nullable=False, unique=True)
    slug = db.Column(db.String(140), unique=True, nullable=False)
    logo_url = db.Column(db.String(500))
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=_now)

    products = db.relationship("Product", backref="brand", lazy="dynamic")

    def save(self):
        if not self.slug:
            self.slug = slugify(self.name)
        db.session.add(self)
        db.session.commit()

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "slug": self.slug,
            "logo_url": self.logo_url, "description": self.description,
        }