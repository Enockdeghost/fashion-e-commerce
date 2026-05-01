from slugify import slugify
from app.extensions import db
from app.models.helpers import _uuid, _now

class Tag(db.Model):
    __tablename__ = "tags"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    name = db.Column(db.String(80), nullable=False, unique=True)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=_now)

    def save(self):
        if not self.slug:
            self.slug = slugify(self.name)
        db.session.add(self)
        db.session.commit()

    def to_dict(self):
        return {"id": self.id, "name": self.name, "slug": self.slug}