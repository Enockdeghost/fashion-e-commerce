from app.extensions import db

product_tags = db.Table(
    "product_tags",
    db.Column("product_id", db.String(36), db.ForeignKey("products.id"), primary_key=True),
    db.Column("tag_id", db.String(36), db.ForeignKey("tags.id"), primary_key=True),
)

product_collections = db.Table(
    "product_collections",
    db.Column("product_id", db.String(36), db.ForeignKey("products.id"), primary_key=True),
    db.Column("collection_id", db.String(36), db.ForeignKey("collections.id"), primary_key=True),
)