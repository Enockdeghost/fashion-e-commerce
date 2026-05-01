
from flask import Blueprint, request, jsonify, g
from sqlalchemy import or_, desc, asc
from app.extensions import db, limiter
from app.models import (
    Product, ProductVariant, ProductImage, ProductVideo,
    Category, Brand, Collection, Tag, InventoryLog,
)
from app.utils.security import (
    admin_required, roles_required, sanitise_text, sanitise_html,
    validate_pagination, ok, err,
)
from app.services.media_service import (
    upload_product_image, upload_product_video, validate_image, validate_video,
    delete_media,
)
from slugify import slugify

products_bp = Blueprint("products", __name__, url_prefix="/products")



@products_bp.route("", methods=["GET"])
def list_products():
    page, per_page = validate_pagination(request.args)
    q = Product.query.filter_by(is_deleted=False, is_active=True)

    # Filters
    if cat := request.args.get("category"):
        q = q.join(Category).filter(or_(Category.id == cat, Category.slug == cat))
    if brand := request.args.get("brand"):
        q = q.join(Brand).filter(or_(Brand.id == brand, Brand.slug == brand))
    if col := request.args.get("collection"):
        q = q.filter(Product.collections.any(or_(Collection.id == col, Collection.slug == col)))
    if tag := request.args.get("tag"):
        q = q.filter(Product.tags.any(or_(Tag.id == tag, Tag.slug == tag)))
    if featured := request.args.get("featured"):
        q = q.filter(Product.is_featured == (featured.lower() == "true"))
    if new_arr := request.args.get("new_arrival"):
        q = q.filter(Product.is_new_arrival == (new_arr.lower() == "true"))
    if bestseller := request.args.get("bestseller"):
        q = q.filter(Product.is_bestseller == (bestseller.lower() == "true"))
    if min_price := request.args.get("min_price"):
        q = q.filter(Product.base_price >= float(min_price))
    if max_price := request.args.get("max_price"):
        q = q.filter(Product.base_price <= float(max_price))
    if search := request.args.get("q"):
        like = f"%{search}%"
        q = q.filter(or_(Product.name.ilike(like), Product.description.ilike(like)))

    # Sort
    sort_map = {
        "price_asc": Product.base_price.asc(),
        "price_desc": Product.base_price.desc(),
        "newest": Product.created_at.desc(),
        "bestseller": Product.total_sold.desc(),
        "name_asc": Product.name.asc(),
    }
    sort_key = request.args.get("sort", "newest")
    q = q.order_by(sort_map.get(sort_key, Product.created_at.desc()))

    paginated = q.paginate(page=page, per_page=per_page, error_out=False)

    return ok({
        "products": [p.to_dict() for p in paginated.items],
        "pagination": {
            "page": page, "per_page": per_page,
            "total": paginated.total, "pages": paginated.pages,
            "has_next": paginated.has_next, "has_prev": paginated.has_prev,
        },
    })


@products_bp.route("/<product_id>", methods=["GET"])
def get_product(product_id):
    product = Product.query.filter(
        (Product.id == product_id) | (Product.slug == product_id),
        Product.is_deleted == False,
    ).first_or_404()

    # Increment view count
    product.view_count = (product.view_count or 0) + 1
    db.session.commit()

    return ok(product.to_dict(full=True))



@products_bp.route("", methods=["POST"])
@admin_required
def create_product():
    data = request.get_json(force=True)

    # Required
    name = sanitise_text(data.get("name", ""))
    price = data.get("base_price")
    if not name:
        return err("Product name is required")
    if not price:
        return err("base_price is required")

    product = Product(
        name=name,
        slug=slugify(name),
        description=sanitise_html(data.get("description", "")),
        short_description=sanitise_text(data.get("short_description", "")),
        base_price=float(price),
        compare_price=float(data["compare_price"]) if data.get("compare_price") else None,
        cost_price=float(data["cost_price"]) if data.get("cost_price") else None,
        currency=data.get("currency", "TZS"),
        category_id=data.get("category_id"),
        brand_id=data.get("brand_id"),
        is_featured=bool(data.get("is_featured", False)),
        is_new_arrival=bool(data.get("is_new_arrival", False)),
        is_bestseller=bool(data.get("is_bestseller", False)),
        weight=data.get("weight"),
        length=data.get("length"), width=data.get("width"), height=data.get("height"),
        meta_title=sanitise_text(data.get("meta_title", "")),
        meta_description=sanitise_text(data.get("meta_description", "")),
        meta_keywords=sanitise_text(data.get("meta_keywords", "")),
    )

    # Ensure slug is unique
    base_slug = product.slug
    counter = 1
    while Product.query.filter_by(slug=product.slug).first():
        product.slug = f"{base_slug}-{counter}"
        counter += 1

    db.session.add(product)
    db.session.flush()  # get product.id

    # Tags
    for tag_name in data.get("tags", []):
        tag = Tag.query.filter_by(name=tag_name).first()
        if not tag:
            tag = Tag(name=tag_name, slug=slugify(tag_name))
            db.session.add(tag)
        product.tags.append(tag)

    # Collections
    for col_id in data.get("collection_ids", []):
        col = Collection.query.get(col_id)
        if col:
            product.collections.append(col)

    # Variants
    for v_data in data.get("variants", []):
        variant = ProductVariant(
            product_id=product.id,
            size=v_data.get("size"),
            color=v_data.get("color"),
            color_hex=v_data.get("color_hex"),
            material=v_data.get("material"),
            price=v_data.get("price"),
            stock=int(v_data.get("stock", 0)),
            weight=v_data.get("weight"),
        )
        db.session.add(variant)

    db.session.commit()
    return ok(product.to_dict(full=True), "Product created", 201)



@products_bp.route("/<product_id>", methods=["PUT"])
@admin_required
def update_product(product_id):
    product = Product.query.filter_by(id=product_id, is_deleted=False).first_or_404()
    data = request.get_json(force=True)

    fields = [
        "name", "description", "short_description", "base_price", "compare_price",
        "cost_price", "currency", "category_id", "brand_id", "is_active",
        "is_featured", "is_new_arrival", "is_bestseller", "weight",
        "length", "width", "height", "meta_title", "meta_description", "meta_keywords",
    ]
    for field in fields:
        if field in data:
            val = data[field]
            if field in ("description",):
                val = sanitise_html(val)
            elif isinstance(val, str):
                val = sanitise_text(val)
            setattr(product, field, val)

    if "name" in data and not data.get("slug"):
        new_slug = slugify(data["name"])
        existing = Product.query.filter(Product.slug == new_slug, Product.id != product_id).first()
        if not existing:
            product.slug = new_slug

    db.session.commit()
    return ok(product.to_dict(full=True), "Product updated")



@products_bp.route("/<product_id>", methods=["DELETE"])
@roles_required("super_admin", "manager")
def delete_product(product_id):
    product = Product.query.filter_by(id=product_id, is_deleted=False).first_or_404()
    product.soft_delete()
    return ok(message="Product deleted")



@products_bp.route("/<product_id>/images", methods=["POST"])
@admin_required
def upload_image(product_id):
    product = Product.query.filter_by(id=product_id, is_deleted=False).first_or_404()

    if "image" not in request.files:
        return err("No image file provided")
    file = request.files["image"]

    valid, msg = validate_image(file)
    if not valid:
        return err(msg)

    is_primary = request.form.get("is_primary", "false").lower() == "true"
    alt_text = sanitise_text(request.form.get("alt_text", product.name))

    result = upload_product_image(file, product_id, is_primary)

    # If set as primary, unset others
    if is_primary:
        ProductImage.query.filter_by(product_id=product_id).update({"is_primary": False})

    img = ProductImage(
        product_id=product_id,
        url=result["url"],
        thumbnail_url=result["thumbnail_url"],
        public_id=result["public_id"],
        alt_text=alt_text,
        is_primary=is_primary,
        sort_order=request.form.get("sort_order", 0),
    )
    db.session.add(img)
    db.session.commit()
    return ok(img.to_dict(), "Image uploaded", 201)


@products_bp.route("/<product_id>/images/<image_id>", methods=["DELETE"])
@admin_required
def delete_image(product_id, image_id):
    img = ProductImage.query.filter_by(id=image_id, product_id=product_id).first_or_404()
    if img.public_id:
        delete_media(img.public_id)
    db.session.delete(img)
    db.session.commit()
    return ok(message="Image deleted")



@products_bp.route("/<product_id>/videos", methods=["POST"])
@admin_required
def upload_video(product_id):
    product = Product.query.filter_by(id=product_id, is_deleted=False).first_or_404()
    if "video" not in request.files:
        return err("No video file provided")
    file = request.files["video"]
    valid, msg = validate_video(file)
    if not valid:
        return err(msg)

    result = upload_product_video(file, product_id)
    video = ProductVideo(
        product_id=product_id,
        url=result["url"],
        thumbnail_url=result["thumbnail_url"],
        public_id=result["public_id"],
        duration_seconds=result["duration_seconds"],
        title=sanitise_text(request.form.get("title", "")),
    )
    db.session.add(video)
    db.session.commit()
    return ok(video.to_dict(), "Video uploaded", 201)



@products_bp.route("/bulk", methods=["POST"])
@roles_required("super_admin", "manager")
def bulk_create():
    products_data = request.get_json(force=True)
    if not isinstance(products_data, list):
        return err("Expected a JSON array of products")

    created, errors = [], []
    for idx, data in enumerate(products_data):
        try:
            product = Product(
                name=sanitise_text(data["name"]),
                base_price=float(data["base_price"]),
                currency=data.get("currency", "TZS"),
                category_id=data.get("category_id"),
                brand_id=data.get("brand_id"),
                description=sanitise_html(data.get("description", "")),
            )
            product.slug = slugify(product.name)
            db.session.add(product)
            db.session.flush()
            for v in data.get("variants", []):
                db.session.add(ProductVariant(
                    product_id=product.id,
                    size=v.get("size"), color=v.get("color"),
                    stock=int(v.get("stock", 0)),
                ))
            created.append(product.to_dict())
        except Exception as e:
            errors.append({"index": idx, "error": str(e)})

    db.session.commit()
    return ok({"created": created, "errors": errors}, f"{len(created)} products created", 201)



@products_bp.route("/<product_id>/variants", methods=["POST"])
@admin_required
def add_variant(product_id):
    product = Product.query.filter_by(id=product_id, is_deleted=False).first_or_404()
    data = request.get_json(force=True)
    variant = ProductVariant(
        product_id=product_id,
        size=data.get("size"), color=data.get("color"),
        color_hex=data.get("color_hex"), material=data.get("material"),
        price=data.get("price"), stock=int(data.get("stock", 0)),
        image_url=data.get("image_url"),
    )
    db.session.add(variant)
    db.session.commit()
    return ok(variant.to_dict(), "Variant added", 201)


@products_bp.route("/<product_id>/variants/<variant_id>", methods=["PUT"])
@admin_required
def update_variant(product_id, variant_id):
    variant = ProductVariant.query.filter_by(id=variant_id, product_id=product_id).first_or_404()
    data = request.get_json(force=True)
    for field in ["size", "color", "color_hex", "material", "price", "image_url", "is_active", "low_stock_threshold"]:
        if field in data:
            setattr(variant, field, data[field])
    db.session.commit()
    return ok(variant.to_dict(), "Variant updated")



cat_bp = Blueprint("categories", __name__, url_prefix="/categories")


@cat_bp.route("", methods=["GET"])
def list_categories():
    cats = Category.query.filter_by(is_active=True, parent_id=None).all()
    return ok([c.to_dict() for c in cats])


@cat_bp.route("", methods=["POST"])
@admin_required
def create_category():
    data = request.get_json(force=True)
    if not data.get("name"):
        return err("Name is required")
    cat = Category(
        name=sanitise_text(data["name"]),
        slug=slugify(data["name"]),
        description=sanitise_text(data.get("description", "")),
        parent_id=data.get("parent_id"),
        sort_order=data.get("sort_order", 0),
    )
    db.session.add(cat)
    db.session.commit()
    return ok(cat.to_dict(), "Category created", 201)


@cat_bp.route("/<cat_id>", methods=["PUT"])
@admin_required
def update_category(cat_id):
    cat = Category.query.get_or_404(cat_id)
    data = request.get_json(force=True)
    for field in ["name", "description", "parent_id", "is_active", "sort_order"]:
        if field in data:
            setattr(cat, field, sanitise_text(str(data[field])) if isinstance(data[field], str) else data[field])
    if "name" in data:
        cat.slug = slugify(data["name"])
    db.session.commit()
    return ok(cat.to_dict(), "Category updated")


@cat_bp.route("/<cat_id>", methods=["DELETE"])
@roles_required("super_admin")
def delete_category(cat_id):
    cat = Category.query.get_or_404(cat_id)
    cat.is_active = False
    db.session.commit()
    return ok(message="Category deactivated")



brand_bp = Blueprint("brands", __name__, url_prefix="/brands")


@brand_bp.route("", methods=["GET"])
def list_brands():
    brands = Brand.query.filter_by(is_active=True).all()
    return ok([b.to_dict() for b in brands])


@brand_bp.route("", methods=["POST"])
@admin_required
def create_brand():
    data = request.get_json(force=True)
    if not data.get("name"):
        return err("Name is required")
    brand = Brand(
        name=sanitise_text(data["name"]),
        slug=slugify(data["name"]),
        description=sanitise_text(data.get("description", "")),
    )
    db.session.add(brand)
    db.session.commit()
    return ok(brand.to_dict(), "Brand created", 201)



col_bp = Blueprint("collections", __name__, url_prefix="/collections")


@col_bp.route("", methods=["GET"])
def list_collections():
    cols = Collection.query.filter_by(is_active=True).all()
    return ok([c.to_dict() for c in cols])


@col_bp.route("", methods=["POST"])
@admin_required
def create_collection():
    data = request.get_json(force=True)
    if not data.get("name"):
        return err("Name is required")
    col = Collection(
        name=sanitise_text(data["name"]),
        slug=slugify(data["name"]),
        description=sanitise_text(data.get("description", "")),
    )
    db.session.add(col)
    db.session.commit()
    return ok(col.to_dict(), "Collection created", 201)



tag_bp = Blueprint("tags", __name__, url_prefix="/tags")


@tag_bp.route("", methods=["GET"])
def list_tags():
    tags = Tag.query.all()
    return ok([t.to_dict() for t in tags])


@tag_bp.route("", methods=["POST"])
@admin_required
def create_tag():
    data = request.get_json(force=True)
    if not data.get("name"):
        return err("Name is required")
    tag = Tag(name=sanitise_text(data["name"]), slug=slugify(data["name"]))
    db.session.add(tag)
    db.session.commit()
    return ok(tag.to_dict(), "Tag created", 201)