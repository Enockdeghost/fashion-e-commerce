from app.extensions import db
from app.models.helpers import _uuid, _now

class AdminUser(db.Model):
    __tablename__ = "admin_users"

    ROLES = ["super_admin", "manager", "staff"]

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    email = db.Column(db.String(200), nullable=False, unique=True)
    password_hash = db.Column(db.String(200), nullable=False)
    first_name = db.Column(db.String(80))
    last_name = db.Column(db.String(80))
    role = db.Column(db.String(20), nullable=False, default="staff")
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=_now)
    updated_at = db.Column(db.DateTime, default=_now, onupdate=_now)

    def set_password(self, password):
        import bcrypt
        self.password_hash = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

    def check_password(self, password):
        import bcrypt
        return bcrypt.checkpw(
            password.encode("utf-8"), self.password_hash.encode("utf-8")
        )

    def has_permission(self, *roles):
        return self.role in roles

    def to_dict(self):
        return {
            "id": self.id, "email": self.email,
            "first_name": self.first_name, "last_name": self.last_name,
            "role": self.role, "is_active": self.is_active,
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }