
import io
import os
import hashlib
import logging
from datetime import datetime, timezone
from functools import wraps
import re
from flask import Blueprint, request, g, current_app
from sqlalchemy import func, cast, Date, extract

from app.extensions import db, limiter
from app.models import (
    AdminUser, Product, ProductVariant, ProductImage,
    Order, OrderItem, Coupon, Banner, BlogPost, Page, FAQ,
    Category, Brand, Collection, InventoryLog, AbandonedCart,
)
from app.utils.security import (
    admin_required, roles_required,
    ok, err,
    sanitise_text, sanitise_html,
    validate_pagination, is_valid_email,
)
from slugify import slugify

log = logging.getLogger(__name__)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin/manage")


MAX_IMAGE_BYTES = 10 * 1024 * 1024     # 10 MB
MAX_VIDEO_BYTES = 200 * 1024 * 1024    # 200 MB

# Magic bytes for allowed image types (first 8 bytes)
_MAGIC = {
    b"\xff\xd8\xff": "jpeg",
    b"\x89PNG\r\n\x1a\n": "png",
    b"RIFF": "webp",          # RIFF????WEBP
    b"GIF87a": "gif",
    b"GIF89a": "gif",
}

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}


def _detect_image_type(data: bytes) -> str | None:
    """Return image type string or None if not a known safe image."""
    for magic, kind in _MAGIC.items():
        if data[:len(magic)] == magic:
            if kind == "webp" and data[8:12] != b"WEBP":
                continue
            return kind
    return None


def _validate_image_file(file_storage) -> tuple[bool, str, bytes]:
    """
    Full image validation:
      - File object present
      - Extension whitelisted
      - Size ≤ MAX_IMAGE_BYTES
      - Magic bytes match a safe image type
    Returns (is_valid, error_message, raw_bytes).
    """
    if not file_storage or file_storage.filename == "":
        return False, "No file selected", b""

    ext = file_storage.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        return False, f"File type '.{ext}' not allowed. Allowed: {ALLOWED_IMAGE_EXTENSIONS}", b""

    raw = file_storage.read()
    file_storage.seek(0)

    if len(raw) > MAX_IMAGE_BYTES:
        mb = MAX_IMAGE_BYTES // 1024 // 1024
        return False, f"File too large — max {mb} MB", b""

    if len(raw) < 8:
        return False, "File too small to be a valid image", b""

    kind = _detect_image_type(raw)
    if kind is None:
        return False, "File content does not match a valid image format", b""

    # Additional PIL verification
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(raw))
        img.verify()
    except Exception:
        return False, "Image file appears corrupt or invalid", b""

    return True, "", raw


def _safe_filename(filename: str) -> str:
    """Strip path traversal and dangerous chars from filename."""
    basename = os.path.basename(filename or "upload")
    safe = "".join(c for c in basename if c.isalnum() or c in "._-")
    return safe[:80] or "upload"



def _audit(action: str, resource: str, resource_id: str = "", detail: str = ""):
    """Write an audit entry. Never raises — audit failure must not break the API."""
    try:
        admin_id = getattr(getattr(g, "admin", None), "id", "unknown")
        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        log.info(
            "AUDIT | admin=%s | ip=%s | action=%s | resource=%s | id=%s | %s",
            admin_id, ip, action, resource, resource_id, detail,
        )
        # Optionally persist to DB (add AuditLog model later if needed)
    except Exception as exc:
        log.error("Audit write failed: %s", exc)



def _upload_to_cloudinary(file_bytes: bytes, folder: str,
                           transformations: list | None = None,
                           public_id: str | None = None) -> dict:
    """
    Upload raw bytes to Cloudinary.
    Returns {"url", "thumbnail_url", "public_id", "width", "height"}.
    Raises RuntimeError if Cloudinary is not configured or upload fails.
    """
    cloud_name = current_app.config.get("CLOUDINARY_CLOUD_NAME")
    api_key = current_app.config.get("CLOUDINARY_API_KEY")
    api_secret = current_app.config.get("CLOUDINARY_API_SECRET")

    if not all([cloud_name, api_key, api_secret]):
        raise RuntimeError(
            "Cloudinary credentials not configured. "
            "Set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET in .env"
        )

    import cloudinary
    import cloudinary.uploader
    cloudinary.config(
        cloud_name=cloud_name, api_key=api_key,
        api_secret=api_secret, secure=True,
    )

    upload_opts = dict(
        folder=folder,
        resource_type="image",
        format="webp",
        overwrite=True,
    )
    if transformations:
        upload_opts["transformation"] = transformations
    if public_id:
        upload_opts["public_id"] = public_id

    result = cloudinary.uploader.upload(io.BytesIO(file_bytes), **upload_opts)

    # Auto-generate a thumbnail URL
    thumb = cloudinary.CloudinaryImage(result["public_id"]).build_url(
        width=400, height=400, crop="fill", quality="auto:good", format="webp"
    )

    return {
        "url": result["secure_url"],
        "thumbnail_url": thumb,
        "public_id": result["public_id"],
        "width": result.get("width"),
        "height": result.get("height"),
        "bytes": result.get("bytes"),
    }


def _delete_from_cloudinary(public_id: str) -> bool:
    """Soft-delete a Cloudinary asset. Returns True on success."""
    try:
        import cloudinary
        import cloudinary.uploader
        cloudinary.config(
            cloud_name=current_app.config.get("CLOUDINARY_CLOUD_NAME"),
            api_key=current_app.config.get("CLOUDINARY_API_KEY"),
            api_secret=current_app.config.get("CLOUDINARY_API_SECRET"),
            secure=True,
        )
        res = cloudinary.uploader.destroy(public_id)
        return res.get("result") == "ok"
    except Exception as exc:
        log.error("Cloudinary delete failed for %s: %s", public_id, exc)
        return False


def _get_image_url(folder: str,
                   transformations: list | None = None,
                   public_id: str | None = None,
                   field_name: str = "file") -> tuple[str | None, str | None, str | None]:
    """
    Tries to resolve an image URL from the current request.
    Priority: 1) file upload  2) image_url JSON field.
    Returns (url, thumbnail_url, public_id) or (None, None, None) if no image.
    Raises ValueError with a human-readable message on validation failure.
    """
    file = request.files.get(field_name)

    if file and file.filename:
        valid, msg, raw = _validate_image_file(file)
        if not valid:
            raise ValueError(msg)
        result = _upload_to_cloudinary(
            raw, folder,
            transformations=transformations,
            public_id=public_id,
        )
        return result["url"], result["thumbnail_url"], result["public_id"]

    # Fall back to URL passed in JSON body
    data = request.get_json(silent=True) or {}
    url = data.get("image_url") or data.get("cover_image_url")
    if url:
        return sanitise_text(url), None, None

    return None, None, None


@admin_bp.route("/dashboard", methods=["GET"])
@admin_required
def dashboard():
    now = datetime.now(timezone.utc)

    # Core stats
    total_orders = Order.query.count()
    total_products = Product.query.filter_by(is_deleted=False).count()
    total_revenue = db.session.query(
        func.coalesce(func.sum(Order.total), 0)
    ).filter(Order.status.in_(["paid", "processing", "shipped", "delivered"])).scalar()

    pending_orders = Order.query.filter_by(status="pending").count()
    delivered_orders = Order.query.filter_by(status="delivered").count()
    cancelled_orders = Order.query.filter_by(status="cancelled").count()

    # Monthly revenue
    monthly_revenue = db.session.query(
        func.coalesce(func.sum(Order.total), 0)
    ).filter(
        Order.status.in_(["paid", "processing", "shipped", "delivered"]),
        extract("month", Order.created_at) == now.month,
        extract("year", Order.created_at) == now.year,
    ).scalar()

    # Low stock count
    low_stock = ProductVariant.query.join(Product).filter(
        Product.is_deleted == False,
        ProductVariant.is_active == True,
        ProductVariant.stock > 0,
        ProductVariant.stock <= ProductVariant.low_stock_threshold,
    ).count()

    out_of_stock = ProductVariant.query.join(Product).filter(
        Product.is_deleted == False,
        ProductVariant.is_active == True,
        ProductVariant.stock <= 0,
    ).count()

    # Daily revenue chart — last 30 days
    daily = db.session.query(
        cast(Order.created_at, Date).label("day"),
        func.sum(Order.total).label("revenue"),
        func.count(Order.id).label("orders"),
    ).filter(
        Order.status.in_(["paid", "processing", "shipped", "delivered"]),
    ).group_by("day").order_by("day").limit(30).all()

    # Top 5 best-selling products
    top_products = db.session.query(
        Product.name, Product.id,
        func.sum(OrderItem.quantity).label("sold"),
        func.sum(OrderItem.line_total).label("revenue"),
    ).join(OrderItem, OrderItem.product_id == Product.id
    ).group_by(Product.id, Product.name
    ).order_by(func.sum(OrderItem.quantity).desc()).limit(5).all()

    # Recent orders
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(8).all()

    # Abandoned carts count
    abandoned = AbandonedCart.query.filter_by(recovered=False).count()

    return ok({
        "stats": {
            "total_revenue": float(total_revenue or 0),
            "monthly_revenue": float(monthly_revenue or 0),
            "total_orders": total_orders,
            "pending_orders": pending_orders,
            "delivered_orders": delivered_orders,
            "cancelled_orders": cancelled_orders,
            "total_products": total_products,
            "low_stock_items": low_stock,
            "out_of_stock_items": out_of_stock,
            "abandoned_carts": abandoned,
        },
        "daily_chart": [
            {
                "date": str(d.day),
                "revenue": float(d.revenue or 0),
                "orders": d.orders,
            }
            for d in daily
        ],
        "top_products": [
            {
                "id": p.id, "name": p.name,
                "sold": int(p.sold),
                "revenue": float(p.revenue or 0),
            }
            for p in top_products
        ],
        "recent_orders": [o.to_dict() for o in recent_orders],
        "server_time": now.isoformat(),
    })



@admin_bp.route("/banners", methods=["GET"])
@admin_required
def list_banners():
    page, per_page = validate_pagination(request.args)
    position = request.args.get("position")
    q = Banner.query.order_by(Banner.sort_order, Banner.created_at.desc())
    if position:
        q = q.filter_by(position=position)
    paginated = q.paginate(page=page, per_page=per_page, error_out=False)
    return ok({
        "banners": [b.to_dict() for b in paginated.items],
        "pagination": {"page": page, "per_page": per_page, "total": paginated.total},
    })


@admin_bp.route("/banners", methods=["POST"])
@roles_required("super_admin", "manager")
@limiter.limit("30 per minute")
def create_banner():
    """
    Accepts multipart/form-data (with 'file' field) OR application/json (with 'image_url').
    Form fields / JSON fields:
      title, subtitle, link_url, link_text, position, sort_order, is_active,
      starts_at, ends_at  (ISO strings)
    """
    # --- resolve image ---
    try:
        url, thumb_url, pub_id = _get_image_url(
            folder="fashion/banners",
            transformations=[{"width": 1920, "height": 800, "crop": "limit", "quality": "auto:good"}],
        )
    except ValueError as e:
        return err(str(e))
    except RuntimeError as e:
        return err(str(e), 503)

    if not url:
        return err("image_url or file upload is required")

    # --- mobile variant (auto-crop) ---
    mobile_url = None
    if pub_id:
        try:
            import cloudinary
            mobile_url = cloudinary.CloudinaryImage(pub_id).build_url(
                width=768, height=500, crop="fill", quality="auto", format="webp"
            )
        except Exception:
            pass

    data = request.form if request.files else (request.get_json(silent=True) or {})

    banner = Banner(
        title=sanitise_text(data.get("title", "")),
        subtitle=sanitise_text(data.get("subtitle", "")),
        image_url=url,
        mobile_image_url=mobile_url or sanitise_text(data.get("mobile_image_url", "") or ""),
        link_url=sanitise_text(data.get("link_url", "") or ""),
        link_text=sanitise_text(data.get("link_text", "") or ""),
        position=sanitise_text(data.get("position", "homepage_hero")),
        sort_order=int(data.get("sort_order", 0) or 0),
        is_active=str(data.get("is_active", "true")).lower() != "false",
        starts_at=_parse_dt(data.get("starts_at")),
        ends_at=_parse_dt(data.get("ends_at")),
    )
    db.session.add(banner)
    db.session.commit()
    _audit("CREATE", "Banner", banner.id, f"title={banner.title}")
    return ok(banner.to_dict(), "Banner created", 201)


@admin_bp.route("/banners/<banner_id>", methods=["PUT"])
@roles_required("super_admin", "manager")
def update_banner(banner_id):
    banner = Banner.query.get_or_404(banner_id)
    old_pub_id = None

    # --- image replacement ---
    if request.files.get("file"):
        try:
            url, thumb, pub_id = _get_image_url(
                folder="fashion/banners",
                transformations=[{"width": 1920, "height": 800, "crop": "limit", "quality": "auto:good"}],
            )
            if url:
                old_pub_id = _extract_public_id(banner.image_url)
                banner.image_url = url
                if pub_id:
                    try:
                        import cloudinary
                        banner.mobile_image_url = cloudinary.CloudinaryImage(pub_id).build_url(
                            width=768, height=500, crop="fill", quality="auto", format="webp"
                        )
                    except Exception:
                        pass
        except (ValueError, RuntimeError) as e:
            return err(str(e))

    data = request.form if request.files else (request.get_json(silent=True) or {})
    text_fields = ["title", "subtitle", "link_url", "link_text", "position"]
    for f in text_fields:
        if f in data:
            setattr(banner, f, sanitise_text(data[f]))
    if "sort_order" in data:
        banner.sort_order = int(data["sort_order"] or 0)
    if "is_active" in data:
        banner.is_active = str(data["is_active"]).lower() not in ("false", "0", "no")
    if "starts_at" in data:
        banner.starts_at = _parse_dt(data["starts_at"])
    if "ends_at" in data:
        banner.ends_at = _parse_dt(data["ends_at"])
    if "image_url" in data and not request.files.get("file"):
        banner.image_url = sanitise_text(data["image_url"])

    db.session.commit()

    # Delete old Cloudinary asset after successful save
    if old_pub_id:
        _delete_from_cloudinary(old_pub_id)

    _audit("UPDATE", "Banner", banner_id)
    return ok(banner.to_dict(), "Banner updated")


@admin_bp.route("/banners/<banner_id>", methods=["DELETE"])
@roles_required("super_admin")
def delete_banner(banner_id):
    banner = Banner.query.get_or_404(banner_id)
    pub_id = _extract_public_id(banner.image_url)
    db.session.delete(banner)
    db.session.commit()
    if pub_id:
        _delete_from_cloudinary(pub_id)
    _audit("DELETE", "Banner", banner_id)
    return ok(message="Banner deleted")


@admin_bp.route("/blog", methods=["GET"])
@admin_required
def list_blog_posts():
    page, per_page = validate_pagination(request.args)
    published = request.args.get("published")
    q = BlogPost.query.order_by(BlogPost.created_at.desc())
    if published is not None:
        q = q.filter_by(is_published=published.lower() == "true")
    paginated = q.paginate(page=page, per_page=per_page, error_out=False)
    return ok({
        "blog_posts": [b.to_dict(full=True) for b in paginated.items],
        "pagination": {"page": page, "per_page": per_page, "total": paginated.total},
    })


@admin_bp.route("/blog", methods=["POST"])
@roles_required("super_admin", "manager")
@limiter.limit("20 per minute")
def create_blog_post():
    """
    Accepts multipart/form-data (file + form fields) or JSON.
    Fields: title*, excerpt, content, is_published, published_at, meta_title, meta_description
    """
    data = request.form if request.files else (request.get_json(silent=True) or {})
    title = sanitise_text(data.get("title", ""))
    if not title:
        return err("title is required")

    post_slug = slugify(title)

    cover_url = None
    try:
        url, _, _ = _get_image_url(
            folder="fashion/blog",
            transformations=[{"width": 1200, "height": 630, "crop": "fill", "quality": "auto:good"}],
            public_id=post_slug,
        )
        cover_url = url
    except (ValueError, RuntimeError) as e:
        return err(str(e))

    post = BlogPost(
        title=title,
        slug=post_slug,
        excerpt=sanitise_text(data.get("excerpt", "")),
        content=sanitise_html(data.get("content", "")),
        cover_image_url=cover_url,
        author_id=g.admin.id,
        is_published=str(data.get("is_published", "false")).lower() == "true",
        published_at=_parse_dt(data.get("published_at")),
        meta_title=sanitise_text(data.get("meta_title", "")),
        meta_description=sanitise_text(data.get("meta_description", "")),
    )
    if post.is_published and not post.published_at:
        post.published_at = datetime.now(timezone.utc)

    db.session.add(post)
    db.session.commit()
    _audit("CREATE", "BlogPost", post.id, f"title={title}")
    return ok(post.to_dict(full=True), "Blog post created", 201)


@admin_bp.route("/blog/<post_id>", methods=["PUT"])
@roles_required("super_admin", "manager")
def update_blog_post(post_id):
    post = BlogPost.query.get_or_404(post_id)
    old_pub_id = None

    if request.files.get("file"):
        try:
            url, _, _ = _get_image_url(
                folder="fashion/blog",
                transformations=[{"width": 1200, "height": 630, "crop": "fill", "quality": "auto:good"}],
                public_id=post.slug,
            )
            if url:
                old_pub_id = _extract_public_id(post.cover_image_url or "")
                post.cover_image_url = url
        except (ValueError, RuntimeError) as e:
            return err(str(e))

    data = request.form if request.files else (request.get_json(silent=True) or {})

    if "title" in data:
        post.title = sanitise_text(data["title"])
        post.slug = slugify(data["title"])
    if "excerpt" in data:
        post.excerpt = sanitise_text(data["excerpt"])
    if "content" in data:
        post.content = sanitise_html(data["content"])
    if "cover_image_url" in data and not request.files.get("file"):
        post.cover_image_url = sanitise_text(data["cover_image_url"])
    if "is_published" in data:
        post.is_published = str(data["is_published"]).lower() == "true"
        if post.is_published and not post.published_at:
            post.published_at = datetime.now(timezone.utc)
    if "meta_title" in data:
        post.meta_title = sanitise_text(data["meta_title"])
    if "meta_description" in data:
        post.meta_description = sanitise_text(data["meta_description"])

    db.session.commit()
    if old_pub_id:
        _delete_from_cloudinary(old_pub_id)

    _audit("UPDATE", "BlogPost", post_id)
    return ok(post.to_dict(full=True), "Blog post updated")


@admin_bp.route("/blog/<post_id>", methods=["DELETE"])
@roles_required("super_admin")
def delete_blog_post(post_id):
    post = BlogPost.query.get_or_404(post_id)
    pub_id = _extract_public_id(post.cover_image_url or "")
    db.session.delete(post)
    db.session.commit()
    if pub_id:
        _delete_from_cloudinary(pub_id)
    _audit("DELETE", "BlogPost", post_id)
    return ok(message="Blog post deleted")


@admin_bp.route("/pages", methods=["GET"])
@admin_required
def list_pages():
    pages = Page.query.order_by(Page.slug).all()
    return ok([p.to_dict() for p in pages])


@admin_bp.route("/pages", methods=["POST"])
@roles_required("super_admin", "manager")
def create_page():
    data = request.get_json(force=True)
    slug = slugify(sanitise_text(data.get("slug", "")))
    title = sanitise_text(data.get("title", ""))
    if not slug or not title:
        return err("slug and title are required")
    if Page.query.filter_by(slug=slug).first():
        return err(f"A page with slug '{slug}' already exists")
    page = Page(
        slug=slug,
        title=title,
        content=sanitise_html(data.get("content", "")),
        is_published=bool(data.get("is_published", True)),
    )
    db.session.add(page)
    db.session.commit()
    _audit("CREATE", "Page", page.id, f"slug={slug}")
    return ok(page.to_dict(), "Page created", 201)


@admin_bp.route("/pages/<page_id>", methods=["PUT"])
@roles_required("super_admin", "manager")
def update_page(page_id):
    page = Page.query.get_or_404(page_id)
    data = request.get_json(force=True)
    if "title" in data:
        page.title = sanitise_text(data["title"])
    if "slug" in data:
        new_slug = slugify(sanitise_text(data["slug"]))
        conflict = Page.query.filter(Page.slug == new_slug, Page.id != page_id).first()
        if conflict:
            return err(f"Slug '{new_slug}' is already used")
        page.slug = new_slug
    if "content" in data:
        page.content = sanitise_html(data["content"])
    if "is_published" in data:
        page.is_published = bool(data["is_published"])
    db.session.commit()
    _audit("UPDATE", "Page", page_id)
    return ok(page.to_dict(), "Page updated")


@admin_bp.route("/pages/<page_id>", methods=["DELETE"])
@roles_required("super_admin")
def delete_page(page_id):
    page = Page.query.get_or_404(page_id)
    db.session.delete(page)
    db.session.commit()
    _audit("DELETE", "Page", page_id)
    return ok(message="Page deleted")

@admin_bp.route("/faqs", methods=["GET"])
@admin_required
def list_faqs():
    page, per_page = validate_pagination(request.args)
    category = request.args.get("category")
    q = FAQ.query.order_by(FAQ.category, FAQ.sort_order)
    if category:
        q = q.filter_by(category=category)
    paginated = q.paginate(page=page, per_page=per_page, error_out=False)
    return ok({
        "faqs": [f.to_dict() for f in paginated.items],
        "pagination": {"page": page, "per_page": per_page, "total": paginated.total},
    })


@admin_bp.route("/faqs", methods=["POST"])
@roles_required("super_admin", "manager")
def create_faq():
    data = request.get_json(force=True)
    question = sanitise_text(data.get("question", ""))
    answer = sanitise_html(data.get("answer", ""))
    if not question or not answer:
        return err("question and answer are required")
    faq = FAQ(
        question=question,
        answer=answer,
        category=sanitise_text(data.get("category", "general")),
        sort_order=int(data.get("sort_order", 0) or 0),
        is_active=bool(data.get("is_active", True)),
    )
    db.session.add(faq)
    db.session.commit()
    _audit("CREATE", "FAQ", faq.id)
    return ok(faq.to_dict(), "FAQ created", 201)


@admin_bp.route("/faqs/<faq_id>", methods=["PUT"])
@roles_required("super_admin", "manager")
def update_faq(faq_id):
    faq = FAQ.query.get_or_404(faq_id)
    data = request.get_json(force=True)
    if "question" in data:
        faq.question = sanitise_text(data["question"])
    if "answer" in data:
        faq.answer = sanitise_html(data["answer"])
    if "category" in data:
        faq.category = sanitise_text(data["category"])
    if "sort_order" in data:
        faq.sort_order = int(data["sort_order"] or 0)
    if "is_active" in data:
        faq.is_active = bool(data["is_active"])
    db.session.commit()
    _audit("UPDATE", "FAQ", faq_id)
    return ok(faq.to_dict(), "FAQ updated")


@admin_bp.route("/faqs/<faq_id>", methods=["DELETE"])
@roles_required("super_admin")
def delete_faq(faq_id):
    faq = FAQ.query.get_or_404(faq_id)
    db.session.delete(faq)
    db.session.commit()
    _audit("DELETE", "FAQ", faq_id)
    return ok(message="FAQ deleted")

@admin_bp.route("/coupons", methods=["GET"])
@admin_required
def list_coupons():
    page, per_page = validate_pagination(request.args)
    active_only = request.args.get("active")
    q = Coupon.query.order_by(Coupon.created_at.desc())
    if active_only == "true":
        q = q.filter_by(is_active=True)
    paginated = q.paginate(page=page, per_page=per_page, error_out=False)
    return ok({
        "coupons": [c.to_dict() for c in paginated.items],
        "pagination": {"page": page, "per_page": per_page, "total": paginated.total},
    })


@admin_bp.route("/coupons", methods=["POST"])
@roles_required("super_admin", "manager")
def create_coupon():
    data = request.get_json(force=True)
    code = sanitise_text(data.get("code", "")).upper().replace(" ", "")
    if not code:
        return err("code is required")
    if len(code) < 3 or len(code) > 30:
        return err("Coupon code must be 3-30 characters")
    if Coupon.query.filter_by(code=code).first():
        return err("Coupon code already exists")
    if data.get("discount_type") not in ("percentage", "fixed"):
        return err("discount_type must be 'percentage' or 'fixed'")
    disc_val = float(data.get("discount_value", 0))
    if disc_val <= 0:
        return err("discount_value must be positive")
    if data.get("discount_type") == "percentage" and disc_val > 100:
        return err("Percentage discount cannot exceed 100")

    coupon = Coupon(
        code=code,
        description=sanitise_text(data.get("description", "")),
        discount_type=data["discount_type"],
        discount_value=disc_val,
        minimum_purchase=float(data.get("minimum_purchase", 0)),
        maximum_discount=float(data["maximum_discount"]) if data.get("maximum_discount") else None,
        usage_limit=int(data["usage_limit"]) if data.get("usage_limit") else None,
        starts_at=_parse_dt(data.get("starts_at")) or datetime.now(timezone.utc),
        expires_at=_parse_dt(data.get("expires_at")),
        is_active=bool(data.get("is_active", True)),
    )
    db.session.add(coupon)
    db.session.commit()
    _audit("CREATE", "Coupon", coupon.id, f"code={code}")
    return ok(coupon.to_dict(), "Coupon created", 201)


@admin_bp.route("/coupons/<coupon_id>", methods=["PUT"])
@roles_required("super_admin", "manager")
def update_coupon(coupon_id):
    coupon = Coupon.query.get_or_404(coupon_id)
    data = request.get_json(force=True)
    if "code" in data:
        coupon.code = sanitise_text(data["code"]).upper().replace(" ", "")
    for field in ["description", "discount_type", "discount_value",
                  "minimum_purchase", "maximum_discount", "usage_limit", "is_active"]:
        if field in data:
            setattr(coupon, field, data[field])
    if "starts_at" in data:
        coupon.starts_at = _parse_dt(data["starts_at"])
    if "expires_at" in data:
        coupon.expires_at = _parse_dt(data["expires_at"])
    db.session.commit()
    _audit("UPDATE", "Coupon", coupon_id)
    return ok(coupon.to_dict(), "Coupon updated")


@admin_bp.route("/coupons/<coupon_id>", methods=["DELETE"])
@roles_required("super_admin")
def delete_coupon(coupon_id):
    coupon = Coupon.query.get_or_404(coupon_id)
    db.session.delete(coupon)
    db.session.commit()
    _audit("DELETE", "Coupon", coupon_id)
    return ok(message="Coupon deleted")


@admin_bp.route("/categories", methods=["GET"])
@admin_required
def list_categories():
    cats = Category.query.order_by(Category.sort_order, Category.name).all()
    return ok([c.to_dict() for c in cats])


@admin_bp.route("/categories", methods=["POST"])
@roles_required("super_admin", "manager")
def create_category():
    data = request.form if request.files else (request.get_json(silent=True) or {})
    name = sanitise_text(data.get("name", ""))
    if not name:
        return err("name is required")

    image_url = None
    try:
        url, _, _ = _get_image_url(
            folder="fashion/categories",
            transformations=[{"width": 800, "height": 600, "crop": "fill", "quality": "auto:good"}],
        )
        image_url = url
    except (ValueError, RuntimeError) as e:
        return err(str(e))

    cat_slug = slugify(name)
    counter = 1
    base_slug = cat_slug
    while Category.query.filter_by(slug=cat_slug).first():
        cat_slug = f"{base_slug}-{counter}"
        counter += 1

    cat = Category(
        name=name,
        slug=cat_slug,
        description=sanitise_text(data.get("description", "")),
        image_url=image_url,
        parent_id=data.get("parent_id") or None,
        sort_order=int(data.get("sort_order", 0) or 0),
        is_active=str(data.get("is_active", "true")).lower() != "false",
    )
    db.session.add(cat)
    db.session.commit()
    _audit("CREATE", "Category", cat.id, f"name={name}")
    return ok(cat.to_dict(), "Category created", 201)


@admin_bp.route("/categories/<cat_id>", methods=["PUT"])
@roles_required("super_admin", "manager")
def update_category(cat_id):
    cat = Category.query.get_or_404(cat_id)
    old_pub_id = None

    if request.files.get("file"):
        try:
            url, _, _ = _get_image_url(
                folder="fashion/categories",
                transformations=[{"width": 800, "height": 600, "crop": "fill", "quality": "auto:good"}],
            )
            if url:
                old_pub_id = _extract_public_id(cat.image_url or "")
                cat.image_url = url
        except (ValueError, RuntimeError) as e:
            return err(str(e))

    data = request.form if request.files else (request.get_json(silent=True) or {})
    if "name" in data:
        cat.name = sanitise_text(data["name"])
        cat.slug = slugify(data["name"])
    if "description" in data:
        cat.description = sanitise_text(data["description"])
    if "sort_order" in data:
        cat.sort_order = int(data["sort_order"] or 0)
    if "is_active" in data:
        cat.is_active = str(data["is_active"]).lower() not in ("false", "0", "no")
    if "image_url" in data and not request.files.get("file"):
        cat.image_url = sanitise_text(data["image_url"])

    db.session.commit()
    if old_pub_id:
        _delete_from_cloudinary(old_pub_id)
    _audit("UPDATE", "Category", cat_id)
    return ok(cat.to_dict(), "Category updated")


@admin_bp.route("/brands", methods=["GET"])
@admin_required
def list_brands():
    brands = Brand.query.order_by(Brand.name).all()
    return ok([b.to_dict() for b in brands])


@admin_bp.route("/brands", methods=["POST"])
@roles_required("super_admin", "manager")
def create_brand():
    data = request.form if request.files else (request.get_json(silent=True) or {})
    name = sanitise_text(data.get("name", ""))
    if not name:
        return err("name is required")

    logo_url = None
    try:
        url, _, _ = _get_image_url(
            folder="fashion/brands",
            transformations=[{"width": 400, "height": 200, "crop": "limit", "quality": "auto"}],
        )
        logo_url = url
    except (ValueError, RuntimeError) as e:
        return err(str(e))

    brand = Brand(
        name=name,
        slug=slugify(name),
        description=sanitise_text(data.get("description", "")),
        logo_url=logo_url,
        is_active=str(data.get("is_active", "true")).lower() != "false",
    )
    db.session.add(brand)
    db.session.commit()
    _audit("CREATE", "Brand", brand.id, f"name={name}")
    return ok(brand.to_dict(), "Brand created", 201)


@admin_bp.route("/brands/<brand_id>", methods=["PUT"])
@roles_required("super_admin", "manager")
def update_brand(brand_id):
    brand = Brand.query.get_or_404(brand_id)
    old_pub_id = None

    if request.files.get("file"):
        try:
            url, _, _ = _get_image_url(
                folder="fashion/brands",
                transformations=[{"width": 400, "height": 200, "crop": "limit", "quality": "auto"}],
            )
            if url:
                old_pub_id = _extract_public_id(brand.logo_url or "")
                brand.logo_url = url
        except (ValueError, RuntimeError) as e:
            return err(str(e))

    data = request.form if request.files else (request.get_json(silent=True) or {})
    if "name" in data:
        brand.name = sanitise_text(data["name"])
        brand.slug = slugify(data["name"])
    if "description" in data:
        brand.description = sanitise_text(data["description"])
    if "is_active" in data:
        brand.is_active = str(data["is_active"]).lower() not in ("false", "0", "no")
    if "logo_url" in data and not request.files.get("file"):
        brand.logo_url = sanitise_text(data["logo_url"])

    db.session.commit()
    if old_pub_id:
        _delete_from_cloudinary(old_pub_id)
    _audit("UPDATE", "Brand", brand_id)
    return ok(brand.to_dict(), "Brand updated")


@admin_bp.route("/brands/<brand_id>", methods=["DELETE"])
@roles_required("super_admin")
def delete_brand(brand_id):
    brand = Brand.query.get_or_404(brand_id)
    pub_id = _extract_public_id(brand.logo_url or "")
    db.session.delete(brand)
    db.session.commit()
    if pub_id:
        _delete_from_cloudinary(pub_id)
    _audit("DELETE", "Brand", brand_id)
    return ok(message="Brand deleted")


@admin_bp.route("/orders", methods=["GET"])
@admin_required
def list_orders():
    page, per_page = validate_pagination(request.args)
    q = Order.query
    if status := request.args.get("status"):
        q = q.filter_by(status=status)
    if search := request.args.get("q"):
        like = f"%{search}%"
        q = q.filter(
            Order.order_number.ilike(like) |
            Order.customer_email.ilike(like) |
            Order.customer_name.ilike(like)
        )
    if date_from := request.args.get("from"):
        q = q.filter(Order.created_at >= _parse_dt(date_from))
    if date_to := request.args.get("to"):
        q = q.filter(Order.created_at <= _parse_dt(date_to))
    q = q.order_by(Order.created_at.desc())
    paginated = q.paginate(page=page, per_page=per_page, error_out=False)
    return ok({
        "orders": [o.to_dict() for o in paginated.items],
        "pagination": {
            "page": page, "per_page": per_page,
            "total": paginated.total, "pages": paginated.pages,
        },
    })


@admin_bp.route("/orders/<order_id>", methods=["GET"])
@admin_required
def get_order(order_id):
    order = Order.query.filter(
        (Order.id == order_id) | (Order.order_number == order_id)
    ).first_or_404()
    return ok(order.to_dict(full=True))


@admin_bp.route("/products", methods=["GET"])
@admin_required
def list_products():
    page, per_page = validate_pagination(request.args)
    q = Product.query.filter_by(is_deleted=False)
    if search := request.args.get("q"):
        like = f"%{search}%"
        q = q.filter(Product.name.ilike(like) | Product.sku.ilike(like))
    if cat := request.args.get("category_id"):
        q = q.filter_by(category_id=cat)
    if active := request.args.get("active"):
        q = q.filter_by(is_active=active.lower() == "true")
    q = q.order_by(Product.created_at.desc())
    paginated = q.paginate(page=page, per_page=per_page, error_out=False)
    return ok({
        "products": [p.to_dict(full=False) for p in paginated.items],
        "pagination": {
            "page": page, "per_page": per_page,
            "total": paginated.total, "pages": paginated.pages,
        },
    })


@admin_bp.route("/admins", methods=["GET"])
@roles_required("super_admin")
def list_admins():
    admins = AdminUser.query.order_by(AdminUser.created_at.desc()).all()
    return ok([a.to_dict() for a in admins])


@admin_bp.route("/admins", methods=["POST"])
@roles_required("super_admin")
@limiter.limit("10 per hour")
def create_admin():
    data = request.get_json(force=True)
    email = sanitise_text(data.get("email", "")).lower().strip()
    password = data.get("password", "")
    role = sanitise_text(data.get("role", "staff"))

    if not is_valid_email(email):
        return err("Valid email is required")
    if len(password) < 10:
        return err("Password must be at least 10 characters")
    if not _password_strong(password):
        return err("Password must contain uppercase, lowercase, a digit, and a special character")
    if role not in AdminUser.ROLES:
        return err(f"Invalid role. Allowed: {AdminUser.ROLES}")
    if AdminUser.query.filter_by(email=email).first():
        return err("An admin with that email already exists")

    admin = AdminUser(
        email=email,
        first_name=sanitise_text(data.get("first_name", "")),
        last_name=sanitise_text(data.get("last_name", "")),
        role=role,
    )
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    _audit("CREATE", "AdminUser", admin.id, f"email={email} role={role}")
    return ok(admin.to_dict(), "Admin user created", 201)


@admin_bp.route("/admins/<admin_id>", methods=["PUT"])
@roles_required("super_admin")
def update_admin(admin_id):
    admin = AdminUser.query.get_or_404(admin_id)
    data = request.get_json(force=True)

    if "email" in data:
        new_email = sanitise_text(data["email"]).lower().strip()
        if not is_valid_email(new_email):
            return err("Invalid email address")
        conflict = AdminUser.query.filter(
            AdminUser.email == new_email, AdminUser.id != admin_id
        ).first()
        if conflict:
            return err("Email already in use")
        admin.email = new_email

    if "first_name" in data:
        admin.first_name = sanitise_text(data["first_name"])
    if "last_name" in data:
        admin.last_name = sanitise_text(data["last_name"])
    if "role" in data:
        if data["role"] not in AdminUser.ROLES:
            return err(f"Invalid role. Allowed: {AdminUser.ROLES}")
        admin.role = data["role"]
    if "is_active" in data:
        if admin.id == g.admin.id and not data["is_active"]:
            return err("You cannot deactivate your own account")
        admin.is_active = bool(data["is_active"])
    if "password" in data:
        new_pw = data["password"]
        if len(new_pw) < 10:
            return err("Password must be at least 10 characters")
        if not _password_strong(new_pw):
            return err("Password must contain uppercase, lowercase, a digit, and a special character")
        admin.set_password(new_pw)

    db.session.commit()
    _audit("UPDATE", "AdminUser", admin_id)
    return ok(admin.to_dict(), "Admin user updated")


@admin_bp.route("/admins/<admin_id>", methods=["DELETE"])
@roles_required("super_admin")
def delete_admin(admin_id):
    if admin_id == g.admin.id:
        return err("You cannot delete your own account")
    admin = AdminUser.query.get_or_404(admin_id)
    db.session.delete(admin)
    db.session.commit()
    _audit("DELETE", "AdminUser", admin_id, f"email={admin.email}")
    return ok(message="Admin user deleted")


@admin_bp.route("/upload", methods=["POST"])
@admin_required
@limiter.limit("60 per minute")
def generic_upload():
    """
    Upload any image and get back a Cloudinary URL.
    Used by frontend rich-text editors and manual URL entry fields.
    Form fields:
      file*     — the image file
      folder    — cloudinary subfolder (default: 'fashion/misc')
    """
    if "file" not in request.files:
        return err("No 'file' field in request")

    folder = sanitise_text(request.form.get("folder", "fashion/misc"))
    # Block path traversal in folder name
    folder = folder.replace("..", "").strip("/").strip()
    if not folder.startswith("fashion/"):
        folder = f"fashion/{folder}"

    file = request.files["file"]
    valid, msg, raw = _validate_image_file(file)
    if not valid:
        return err(msg)

    try:
        result = _upload_to_cloudinary(raw, folder)
    except RuntimeError as e:
        return err(str(e), 503)

    _audit("UPLOAD", "Media", result["public_id"], f"folder={folder} bytes={len(raw)}")
    return ok({
        "url": result["url"],
        "thumbnail_url": result["thumbnail_url"],
        "public_id": result["public_id"],
        "width": result["width"],
        "height": result["height"],
    }, "Image uploaded", 201)


@admin_bp.route("/upload/<public_id>", methods=["DELETE"])
@roles_required("super_admin", "manager")
def delete_upload(public_id):
    """Delete a Cloudinary asset by its public_id."""
    # Validate: only allow deletion of assets under our fashion/ namespace
    safe_id = sanitise_text(public_id)
    if not safe_id.startswith("fashion/"):
        return err("Can only delete assets under the 'fashion/' namespace", 403)
    success = _delete_from_cloudinary(safe_id)
    if not success:
        return err("Delete failed or asset not found", 404)
    _audit("DELETE", "Media", safe_id)
    return ok(message="Asset deleted")


@admin_bp.route("/analytics/revenue", methods=["GET"])
@admin_required
def revenue_analytics():
    """Monthly revenue breakdown for the current year."""
    year = int(request.args.get("year", datetime.now(timezone.utc).year))
    monthly = db.session.query(
        extract("month", Order.created_at).label("month"),
        func.sum(Order.total).label("revenue"),
        func.count(Order.id).label("orders"),
    ).filter(
        Order.status.in_(["paid", "processing", "shipped", "delivered"]),
        extract("year", Order.created_at) == year,
    ).group_by("month").order_by("month").all()

    return ok({
        "year": year,
        "monthly": [
            {"month": int(r.month), "revenue": float(r.revenue or 0), "orders": r.orders}
            for r in monthly
        ],
    })


@admin_bp.route("/analytics/top-products", methods=["GET"])
@admin_required
def top_products():
    limit = min(int(request.args.get("limit", 10)), 50)
    rows = db.session.query(
        Product.id, Product.name,
        func.sum(OrderItem.quantity).label("units_sold"),
        func.sum(OrderItem.line_total).label("revenue"),
    ).join(OrderItem, OrderItem.product_id == Product.id
    ).group_by(Product.id, Product.name
    ).order_by(func.sum(OrderItem.quantity).desc()).limit(limit).all()
    return ok([
        {"id": r.id, "name": r.name,
         "units_sold": int(r.units_sold or 0),
         "revenue": float(r.revenue or 0)}
        for r in rows
    ])



def _parse_dt(value) -> datetime | None:
    """Safely parse an ISO datetime string."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def _extract_public_id(url: str) -> str | None:
   
    if not url or "res.cloudinary.com" not in url:
        return None
    try:
        # Everything after /upload/vXXXX/ or /upload/
        parts = url.split("/upload/")
        if len(parts) < 2:
            return None
        path = parts[1]
        # Strip version prefix vNNNN/
        if path.startswith("v") and "/" in path:
            path = path.split("/", 1)[1]
        # Strip extension
        if "." in path.rsplit("/", 1)[-1]:
            path = path.rsplit(".", 1)[0]
        return path
    except Exception:
        return None


def _password_strong(pw: str) -> bool:
   
    return bool(
        re.search(r"[A-Z]", pw) and
        re.search(r"[a-z]", pw) and
        re.search(r"\d", pw) and
        re.search(r"[!@#$%^&*(),.?\":{}|<>\-_+=\[\]\\;'/`~]", pw)
    )