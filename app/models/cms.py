from app.extensions import db
from app.models.helpers import _uuid, _now
from slugify import slugify

class Banner(db.Model):
    __tablename__ = "banners"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    title = db.Column(db.String(200))
    subtitle = db.Column(db.String(300))
    image_url = db.Column(db.String(500), nullable=False)
    mobile_image_url = db.Column(db.String(500))
    link_url = db.Column(db.String(500))
    link_text = db.Column(db.String(100))
    position = db.Column(db.String(50), default="homepage_hero")
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    starts_at = db.Column(db.DateTime)
    ends_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=_now)

    def to_dict(self):
        return {
            "id": self.id, "title": self.title, "subtitle": self.subtitle,
            "image_url": self.image_url, "mobile_image_url": self.mobile_image_url,
            "link_url": self.link_url, "link_text": self.link_text,
            "position": self.position, "sort_order": self.sort_order,
        }


class BlogPost(db.Model):
    __tablename__ = "blog_posts"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    title = db.Column(db.String(300), nullable=False)
    slug = db.Column(db.String(350), unique=True, nullable=False)
    excerpt = db.Column(db.String(500))
    content = db.Column(db.Text)
    cover_image_url = db.Column(db.String(500))
    author_id = db.Column(db.String(36), db.ForeignKey("admin_users.id"), nullable=True)
    is_published = db.Column(db.Boolean, default=False)
    published_at = db.Column(db.DateTime)
    meta_title = db.Column(db.String(200))
    meta_description = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=_now)
    updated_at = db.Column(db.DateTime, default=_now, onupdate=_now)

    author = db.relationship("AdminUser")

    def save(self):
        if not self.slug:
            self.slug = slugify(self.title)
        db.session.add(self)
        db.session.commit()

    def to_dict(self, full=False):
        data = {
            "id": self.id, "title": self.title, "slug": self.slug,
            "excerpt": self.excerpt, "cover_image_url": self.cover_image_url,
            "is_published": self.is_published,
            "published_at": self.published_at.isoformat() if self.published_at else None,
        }
        if full:
            data["content"] = self.content
        return data


class Page(db.Model):
    __tablename__ = "pages"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text)
    is_published = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=_now)
    updated_at = db.Column(db.DateTime, default=_now, onupdate=_now)

    def to_dict(self):
        return {
            "id": self.id, "slug": self.slug, "title": self.title,
            "content": self.content, "is_published": self.is_published,
        }


class FAQ(db.Model):
    __tablename__ = "faqs"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    question = db.Column(db.String(500), nullable=False)
    answer = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(80), default="general")
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=_now)

    def to_dict(self):
        return {
            "id": self.id, "question": self.question, "answer": self.answer,
            "category": self.category, "sort_order": self.sort_order,
        }