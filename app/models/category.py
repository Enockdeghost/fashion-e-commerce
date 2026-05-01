from slugify import slugify
from app.extensions import db
from app.models.helpers import _uuid, _now

class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    name = db.Column(db.String(120), nullable=False, unique=True)
    slug = db.Column(db.String(140), unique=True, nullable=False)
    description = db.Column(db.Text)
    image_url = db.Column(db.String(500))
    parent_id = db.Column(db.String(36), db.ForeignKey("categories.id"), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=_now)
    updated_at = db.Column(db.DateTime, default=_now, onupdate=_now)

    subcategories = db.relationship("Category", backref=db.backref("parent", remote_side=[id]))
    products = db.relationship("Product", backref="category", lazy="dynamic")

    def save(self):
        if not self.slug:
            self.slug = slugify(self.name)
        db.session.add(self)
        db.session.commit()

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "slug": self.slug,
            "description": self.description, "image_url": self.image_url,
            "parent_id": self.parent_id, "is_active": self.is_active,
            "sort_order": self.sort_order,
            "subcategories": [s.to_dict() for s in self.subcategories],
        }