from datetime import datetime, timezone
from flask import Blueprint, request, g
from app.extensions import db
from app.models import (
    Order, Product, Coupon, Banner, BlogPost, Page, FAQ, AdminUser,
    ProductVariant
)
from app.utils.security import (
    admin_required, roles_required, ok, err,
    sanitise_text, sanitise_html, validate_pagination,
)
from slugify import slugify

admin_bp = Blueprint("admin", __name__, url_prefix="/admin/manage")


# ── Dashboard 
@admin_bp.route("/dashboard", methods=["GET"])
@admin_required
def dashboard():
    now = datetime.now(timezone.utc)
    total_orders = Order.query.count()
    total_products = Product.query.filter_by(is_deleted=False).count()
    total_revenue = db.session.query(db.func.sum(Order.total)).filter(
        Order.status.in_(["paid", "processing", "shipped", "delivered"])
    ).scalar() or 0.0
    low_stock_count = ProductVariant.query.join(Product).filter(
        Product.is_deleted == False,
        ProductVariant.is_active == True,
        ProductVariant.stock <= ProductVariant.low_stock_threshold,
        ProductVariant.stock > 0
    ).count()
    pending_orders = Order.query.filter_by(status="pending").count()

    return ok({
        "total_orders": total_orders,
        "total_products": total_products,
        "total_revenue": float(total_revenue),
        "low_stock_count": low_stock_count,
        "pending_orders": pending_orders,
        "server_time": now.isoformat(),
    })


# ── Coupons CRUD 
@admin_bp.route("/coupons", methods=["GET"])
@admin_required
def list_coupons():
    page, per_page = validate_pagination(request.args)
    q = Coupon.query.order_by(Coupon.created_at.desc())
    paginated = q.paginate(page=page, per_page=per_page, error_out=False)
    return ok({
        "coupons": [c.to_dict() for c in paginated.items],
        "pagination": {"page": page, "per_page": per_page, "total": paginated.total},
    })


@admin_bp.route("/coupons", methods=["POST"])
@roles_required("super_admin", "manager")
def create_coupon():
    data = request.get_json(force=True)
    code = sanitise_text(data.get("code", "")).upper()
    if not code:
        return err("code is required")
    if Coupon.query.filter_by(code=code).first():
        return err("Coupon code already exists")

    coupon = Coupon(
        code=code,
        description=sanitise_text(data.get("description", "")),
        discount_type=data["discount_type"],
        discount_value=float(data["discount_value"]),
        minimum_purchase=float(data.get("minimum_purchase", 0)),
        maximum_discount=float(data["maximum_discount"]) if data.get("maximum_discount") else None,
        usage_limit=data.get("usage_limit"),
        starts_at=datetime.fromisoformat(data["starts_at"]) if data.get("starts_at") else datetime.now(timezone.utc),
        expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
        is_active=data.get("is_active", True),
    )
    db.session.add(coupon)
    db.session.commit()
    return ok(coupon.to_dict(), "Coupon created", 201)


@admin_bp.route("/coupons/<coupon_id>", methods=["PUT"])
@roles_required("super_admin", "manager")
def update_coupon(coupon_id):
    coupon = Coupon.query.get_or_404(coupon_id)
    data = request.get_json(force=True)
    for field in ["description", "discount_type", "discount_value", "minimum_purchase",
                  "maximum_discount", "usage_limit", "starts_at", "expires_at", "is_active"]:
        if field in data:
            value = data[field]
            if field in ("starts_at", "expires_at") and value:
                value = datetime.fromisoformat(value)
            setattr(coupon, field, value)
    if "code" in data:
        coupon.code = sanitise_text(data["code"]).upper()
    db.session.commit()
    return ok(coupon.to_dict(), "Coupon updated")


@admin_bp.route("/coupons/<coupon_id>", methods=["DELETE"])
@roles_required("super_admin")
def delete_coupon(coupon_id):
    coupon = Coupon.query.get_or_404(coupon_id)
    db.session.delete(coupon)
    db.session.commit()
    return ok(message="Coupon deleted")


# ── Banners CRUD 
@admin_bp.route("/banners", methods=["GET"])
@admin_required
def list_banners():
    page, per_page = validate_pagination(request.args)
    q = Banner.query.order_by(Banner.sort_order)
    paginated = q.paginate(page=page, per_page=per_page, error_out=False)
    return ok({
        "banners": [b.to_dict() for b in paginated.items],
        "pagination": {"page": page, "total": paginated.total},
    })


@admin_bp.route("/banners", methods=["POST"])
@roles_required("super_admin", "manager")
def create_banner():
    data = request.get_json(force=True)
    if not data.get("image_url"):
        return err("image_url is required")
    banner = Banner(
        title=sanitise_text(data.get("title", "")),
        subtitle=sanitise_text(data.get("subtitle", "")),
        image_url=data["image_url"],
        mobile_image_url=data.get("mobile_image_url"),
        link_url=data.get("link_url"),
        link_text=sanitise_text(data.get("link_text", "")),
        position=data.get("position", "homepage_hero"),
        sort_order=int(data.get("sort_order", 0)),
        is_active=data.get("is_active", True),
        starts_at=datetime.fromisoformat(data["starts_at"]) if data.get("starts_at") else None,
        ends_at=datetime.fromisoformat(data["ends_at"]) if data.get("ends_at") else None,
    )
    db.session.add(banner)
    db.session.commit()
    return ok(banner.to_dict(), "Banner created", 201)


@admin_bp.route("/banners/<banner_id>", methods=["PUT"])
@roles_required("super_admin", "manager")
def update_banner(banner_id):
    banner = Banner.query.get_or_404(banner_id)
    data = request.get_json(force=True)
    for field in ["title", "subtitle", "image_url", "mobile_image_url", "link_url",
                  "link_text", "position", "sort_order", "is_active", "starts_at", "ends_at"]:
        if field in data:
            val = data[field]
            if field in ("starts_at", "ends_at") and val:
                val = datetime.fromisoformat(val)
            setattr(banner, field, val)
    db.session.commit()
    return ok(banner.to_dict(), "Banner updated")


@admin_bp.route("/banners/<banner_id>", methods=["DELETE"])
@roles_required("super_admin")
def delete_banner(banner_id):
    banner = Banner.query.get_or_404(banner_id)
    db.session.delete(banner)
    db.session.commit()
    return ok(message="Banner deleted")


# ── Blog Posts CRUD 

@admin_bp.route("/blog", methods=["GET"])
@admin_required
def list_blog_posts():
    page, per_page = validate_pagination(request.args)
    q = BlogPost.query.order_by(BlogPost.created_at.desc())
    paginated = q.paginate(page=page, per_page=per_page, error_out=False)
    return ok({
        "blog_posts": [b.to_dict(full=True) for b in paginated.items],
        "pagination": {"page": page, "per_page": per_page, "total": paginated.total},
    })


@admin_bp.route("/blog", methods=["POST"])
@roles_required("super_admin", "manager")
def create_blog_post():
    data = request.get_json(force=True)
    if not data.get("title"):
        return err("title is required")
    post = BlogPost(
        title=sanitise_text(data["title"]),
        slug=slugify(data["title"]),
        excerpt=sanitise_text(data.get("excerpt", "")),
        content=sanitise_html(data.get("content", "")),
        cover_image_url=data.get("cover_image_url"),
        author_id=g.admin.id,
        is_published=data.get("is_published", False),
        published_at=datetime.fromisoformat(data["published_at"]) if data.get("published_at") else None,
        meta_title=sanitise_text(data.get("meta_title", "")),
        meta_description=sanitise_text(data.get("meta_description", "")),
    )
    db.session.add(post)
    db.session.commit()
    return ok(post.to_dict(full=True), "Blog post created", 201)


@admin_bp.route("/blog/<post_id>", methods=["PUT"])
@roles_required("super_admin", "manager")
def update_blog_post(post_id):
    post = BlogPost.query.get_or_404(post_id)
    data = request.get_json(force=True)
    for field in ["title", "excerpt", "content", "cover_image_url", "is_published",
                  "published_at", "meta_title", "meta_description"]:
        if field in data:
            val = data[field]
            if field == "published_at" and val:
                val = datetime.fromisoformat(val)
            setattr(post, field, sanitise_text(val) if isinstance(val, str) else val)
    if "title" in data:
        post.slug = slugify(data["title"])
    db.session.commit()
    return ok(post.to_dict(full=True), "Blog post updated")


@admin_bp.route("/blog/<post_id>", methods=["DELETE"])
@roles_required("super_admin")
def delete_blog_post(post_id):
    post = BlogPost.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    return ok(message="Blog post deleted")


# ── Pages CRUD 
@admin_bp.route("/pages", methods=["GET"])
@admin_required
def list_pages():
    pages = Page.query.all()
    return ok([p.to_dict() for p in pages])


@admin_bp.route("/pages", methods=["POST"])
@roles_required("super_admin", "manager")
def create_page():
    data = request.get_json(force=True)
    if not data.get("slug") or not data.get("title"):
        return err("slug and title are required")
    page = Page(
        slug=slugify(data["slug"]),
        title=sanitise_text(data["title"]),
        content=sanitise_html(data.get("content", "")),
        is_published=data.get("is_published", True),
    )
    db.session.add(page)
    db.session.commit()
    return ok(page.to_dict(), "Page created", 201)


@admin_bp.route("/pages/<page_id>", methods=["PUT"])
@roles_required("super_admin", "manager")
def update_page(page_id):
    page = Page.query.get_or_404(page_id)
    data = request.get_json(force=True)
    for field in ["slug", "title", "content", "is_published"]:
        if field in data:
            val = data[field]
            if field in ("title", "content"):
                val = sanitise_text(val) if field == "title" else sanitise_html(val)
            setattr(page, field, val)
    db.session.commit()
    return ok(page.to_dict(), "Page updated")


@admin_bp.route("/pages/<page_id>", methods=["DELETE"])
@roles_required("super_admin")
def delete_page(page_id):
    page = Page.query.get_or_404(page_id)
    db.session.delete(page)
    db.session.commit()
    return ok(message="Page deleted")


# ── FAQs CRUD 
@admin_bp.route("/faqs", methods=["GET"])
@admin_required
def list_faqs():
    page, per_page = validate_pagination(request.args)
    q = FAQ.query.order_by(FAQ.sort_order)
    paginated = q.paginate(page=page, per_page=per_page, error_out=False)
    return ok({
        "faqs": [f.to_dict() for f in paginated.items],
        "pagination": {"page": page, "total": paginated.total},
    })


@admin_bp.route("/faqs", methods=["POST"])
@roles_required("super_admin", "manager")
def create_faq():
    data = request.get_json(force=True)
    if not data.get("question") or not data.get("answer"):
        return err("question and answer are required")
    faq = FAQ(
        question=sanitise_text(data["question"]),
        answer=sanitise_html(data["answer"]),
        category=sanitise_text(data.get("category", "general")),
        sort_order=int(data.get("sort_order", 0)),
    )
    db.session.add(faq)
    db.session.commit()
    return ok(faq.to_dict(), "FAQ created", 201)


@admin_bp.route("/faqs/<faq_id>", methods=["PUT"])
@roles_required("super_admin", "manager")
def update_faq(faq_id):
    faq = FAQ.query.get_or_404(faq_id)
    data = request.get_json(force=True)
    for field in ["question", "answer", "category", "sort_order", "is_active"]:
        if field in data:
            val = data[field]
            if field == "question":
                val = sanitise_text(val)
            elif field == "answer":
                val = sanitise_html(val)
            setattr(faq, field, val)
    db.session.commit()
    return ok(faq.to_dict(), "FAQ updated")


@admin_bp.route("/faqs/<faq_id>", methods=["DELETE"])
@roles_required("super_admin")
def delete_faq(faq_id):
    faq = FAQ.query.get_or_404(faq_id)
    db.session.delete(faq)
    db.session.commit()
    return ok(message="FAQ deleted")


# ── Admin Users Management (super_admin only) 

@admin_bp.route("/admins", methods=["GET"])
@roles_required("super_admin")
def list_admins():
    admins = AdminUser.query.all()
    return ok([a.to_dict() for a in admins])


@admin_bp.route("/admins", methods=["POST"])
@roles_required("super_admin")
def create_admin():
    data = request.get_json(force=True)
    email = sanitise_text(data.get("email", "")).lower().strip()
    password = data.get("password")
    if not email or not password:
        return err("email and password are required")
    if AdminUser.query.filter_by(email=email).first():
        return err("Admin already exists")

    admin = AdminUser(
        email=email,
        first_name=sanitise_text(data.get("first_name", "")),
        last_name=sanitise_text(data.get("last_name", "")),
        role=data.get("role", "staff"),
    )
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    return ok(admin.to_dict(), "Admin created", 201)


@admin_bp.route("/admins/<admin_id>", methods=["PUT"])
@roles_required("super_admin")
def update_admin(admin_id):
    admin = AdminUser.query.get_or_404(admin_id)
    data = request.get_json(force=True)
    if "email" in data:
        admin.email = sanitise_text(data["email"]).lower().strip()
    if "first_name" in data:
        admin.first_name = sanitise_text(data["first_name"])
    if "last_name" in data:
        admin.last_name = sanitise_text(data["last_name"])
    if "role" in data:
        admin.role = data["role"]
    if "password" in data:
        admin.set_password(data["password"])
    if "is_active" in data:
        admin.is_active = bool(data["is_active"])
    db.session.commit()
    return ok(admin.to_dict(), "Admin updated")


@admin_bp.route("/admins/<admin_id>", methods=["DELETE"])
@roles_required("super_admin")
def delete_admin(admin_id):
    admin = AdminUser.query.get_or_404(admin_id)
    if admin.id == g.admin.id:
        return err("You cannot delete your own account", 400)
    db.session.delete(admin)
    db.session.commit()
    return ok(message="Admin deleted")