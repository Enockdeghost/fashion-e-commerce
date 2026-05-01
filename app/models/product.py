from slugify import slugify
from app.extensions import db
from app.models.helpers import _uuid, _now, _gen_sku
from app.models.associations import product_tags, product_collections

class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(300), unique=True, nullable=False)
    description = db.Column(db.Text)
    short_description = db.Column(db.String(500))
    sku = db.Column(db.String(50), unique=True, nullable=False, default=_gen_sku)
    base_price = db.Column(db.Numeric(12, 2), nullable=False)
    compare_price = db.Column(db.Numeric(12, 2))
    cost_price = db.Column(db.Numeric(12, 2))
    currency = db.Column(db.String(3), default="TZS")

    category_id = db.Column(db.String(36), db.ForeignKey("categories.id"), nullable=True)
    brand_id = db.Column(db.String(36), db.ForeignKey("brands.id"), nullable=True)

    is_active = db.Column(db.Boolean, default=True)
    is_deleted = db.Column(db.Boolean, default=False)
    is_featured = db.Column(db.Boolean, default=False)
    is_new_arrival = db.Column(db.Boolean, default=False)
    is_bestseller = db.Column(db.Boolean, default=False)

    meta_title = db.Column(db.String(200))
    meta_description = db.Column(db.String(300))
    meta_keywords = db.Column(db.String(300))

    weight = db.Column(db.Float)
    length = db.Column(db.Float)
    width = db.Column(db.Float)
    height = db.Column(db.Float)

    total_sold = db.Column(db.Integer, default=0)
    view_count = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=_now)
    updated_at = db.Column(db.DateTime, default=_now, onupdate=_now)
    deleted_at = db.Column(db.DateTime, nullable=True)

    variants = db.relationship("ProductVariant", backref="product", lazy="dynamic",
                               cascade="all, delete-orphan")
    images = db.relationship("ProductImage", backref="product", lazy="dynamic",
                             cascade="all, delete-orphan")
    videos = db.relationship("ProductVideo", backref="product", lazy="dynamic",
                             cascade="all, delete-orphan")
    tags = db.relationship("Tag", secondary=product_tags, lazy="subquery",
                           backref=db.backref("products", lazy=True))
    collections = db.relationship("Collection", secondary=product_collections, lazy="subquery",
                                  backref=db.backref("products", lazy=True))

    def save(self):
        if not self.slug:
            self.slug = slugify(self.name)
        db.session.add(self)
        db.session.commit()

    def soft_delete(self):
        self.is_deleted = True
        self.is_active = False
        self.deleted_at = _now()
        db.session.commit()

    @property
    def primary_image(self):
        img = self.images.filter_by(is_primary=True).first()
        return img.url if img else None

    @property
    def total_stock(self):
        return sum(v.stock for v in self.variants)

    def to_dict(self, full=False):
        data = {
            "id": self.id, "name": self.name, "slug": self.slug,
            "sku": self.sku,
            "base_price": float(self.base_price),
            "compare_price": float(self.compare_price) if self.compare_price else None,
            "currency": self.currency,
            "is_active": self.is_active, "is_featured": self.is_featured,
            "is_new_arrival": self.is_new_arrival, "is_bestseller": self.is_bestseller,
            "category": self.category.to_dict() if self.category else None,
            "brand": self.brand.to_dict() if self.brand else None,
            "primary_image": self.primary_image,
            "total_stock": self.total_stock,
            "created_at": self.created_at.isoformat(),
        }
        if full:
            data.update({
                "description": self.description,
                "short_description": self.short_description,
                "cost_price": float(self.cost_price) if self.cost_price else None,
                "weight": self.weight,
                "tags": [t.to_dict() for t in self.tags],
                "collections": [c.to_dict() for c in self.collections],
                "variants": [v.to_dict() for v in self.variants],
                "images": [i.to_dict() for i in self.images],
                "videos": [v.to_dict() for v in self.videos],
                "meta_title": self.meta_title,
                "meta_description": self.meta_description,
                "total_sold": self.total_sold,
                "view_count": self.view_count,
            })
        return data


class ProductVariant(db.Model):
    __tablename__ = "product_variants"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    product_id = db.Column(db.String(36), db.ForeignKey("products.id"), nullable=False)
    sku = db.Column(db.String(60), unique=True, nullable=False, default=_gen_sku)
    size = db.Column(db.String(20))
    color = db.Column(db.String(50))
    color_hex = db.Column(db.String(10))
    material = db.Column(db.String(100))
    price = db.Column(db.Numeric(12, 2))
    stock = db.Column(db.Integer, default=0)
    reserved_stock = db.Column(db.Integer, default=0)
    low_stock_threshold = db.Column(db.Integer, default=5)
    weight = db.Column(db.Float)
    is_active = db.Column(db.Boolean, default=True)
    image_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=_now)
    updated_at = db.Column(db.DateTime, default=_now, onupdate=_now)

    inventory_logs = db.relationship("InventoryLog", backref="variant", lazy="dynamic")

    @property
    def available_stock(self):
        return max(0, self.stock - self.reserved_stock)

    @property
    def is_low_stock(self):
        return 0 < self.available_stock <= self.low_stock_threshold

    @property
    def is_out_of_stock(self):
        return self.available_stock <= 0

    def to_dict(self):
        return {
            "id": self.id, "product_id": self.product_id,
            "sku": self.sku, "size": self.size, "color": self.color,
            "color_hex": self.color_hex, "material": self.material,
            "price": float(self.price) if self.price else None,
            "stock": self.stock, "reserved_stock": self.reserved_stock,
            "available_stock": self.available_stock,
            "is_low_stock": self.is_low_stock,
            "is_out_of_stock": self.is_out_of_stock,
            "image_url": self.image_url, "is_active": self.is_active,
        }


class ProductImage(db.Model):
    __tablename__ = "product_images"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    product_id = db.Column(db.String(36), db.ForeignKey("products.id"), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    thumbnail_url = db.Column(db.String(500))
    alt_text = db.Column(db.String(200))
    is_primary = db.Column(db.Boolean, default=False)
    sort_order = db.Column(db.Integer, default=0)
    public_id = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=_now)

    def to_dict(self):
        return {
            "id": self.id, "url": self.url, "thumbnail_url": self.thumbnail_url,
            "alt_text": self.alt_text, "is_primary": self.is_primary,
            "sort_order": self.sort_order,
        }


class ProductVideo(db.Model):
    __tablename__ = "product_videos"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    product_id = db.Column(db.String(36), db.ForeignKey("products.id"), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    thumbnail_url = db.Column(db.String(500))
    title = db.Column(db.String(200))
    duration_seconds = db.Column(db.Integer)
    public_id = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=_now)

    def to_dict(self):
        return {
            "id": self.id, "url": self.url, "thumbnail_url": self.thumbnail_url,
            "title": self.title, "duration_seconds": self.duration_seconds,
        }