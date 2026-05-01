from app.extensions import db
from app.models.helpers import _uuid, _now


class Media(db.Model):
    __tablename__ = "media"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    url = db.Column(db.String(500), nullable=False)
    secure_url = db.Column(db.String(500))
    public_id = db.Column(db.String(200))       # Cloudinary public_id
    resource_type = db.Column(db.String(10), default="image")   # "image" / "video"
    width = db.Column(db.Integer)
    height = db.Column(db.Integer)
    format = db.Column(db.String(10))
    uploaded_by = db.Column(db.String(36), db.ForeignKey("admin_users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=_now)

    def to_dict(self):
        return {
            "id": self.id,
            "url": self.url,
            "secure_url": self.secure_url,
            "public_id": self.public_id,
            "resource_type": self.resource_type,
            "width": self.width,
            "height": self.height,
            "format": self.format,
            "created_at": self.created_at.isoformat(),
        }