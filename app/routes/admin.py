from flask import Blueprint, request, g
from datetime import datetime, timezone
from slugify import slugify
from app.extensions import db
from app.models import (
    AdminUser, Product, ProductVariant, Order, OrderItem,
    Coupon, Banner, BlogPost, Page, FAQ, Category, Brand, AbandonedCart,
    SiteSettings,
)
from app.utils.security import (
    admin_required, roles_required, ok, err,
    sanitise_text, sanitise_html, validate_pagination,
)
from app.utils.image_utils import convert_to_webp
from sqlalchemy import func, extract
import os, uuid, json
from werkzeug.utils import secure_filename


admin_bp = Blueprint("admin", __name__, url_prefix="/admin/manage")

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'static', 'uploads', 'banners')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ─── DASHBOARD ────────────────────────────────────
@admin_bp.route("/dashboard", methods=["GET"])
@admin_required
def dashboard():
    now = datetime.now(timezone.utc)
    total_orders = Order.query.count()
    total_products = Product.query.filter_by(is_deleted=False).count()
    total_revenue = db.session.query(func.coalesce(func.sum(Order.total), 0)).filter(
        Order.status.in_(["paid", "processing", "shipped", "delivered"])
    ).scalar() or 0.0
    pending_orders = Order.query.filter_by(status="pending").count()
    low_stock = ProductVariant.query.join(Product).filter(
        Product.is_deleted == False,
        ProductVariant.is_active == True,
        ProductVariant.stock > 0,
        ProductVariant.stock <= ProductVariant.low_stock_threshold,
    ).count()
    abandoned = AbandonedCart.query.filter_by(recovered=False).count()
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(8).all()

    return ok({
        "stats": {
            "total_revenue": float(total_revenue),
            "total_orders": total_orders,
            "pending_orders": pending_orders,
            "total_products": total_products,
            "low_stock_items": low_stock,
            "abandoned_carts": abandoned,
            "monthly_revenue": 0,
        },
        "daily_chart": [],
        "top_products": [],
        "recent_orders": [o.to_dict() for o in recent_orders],
        "server_time": now.isoformat(),
    })

# ─── PRODUCTS ─────────────────────────────────────
@admin_bp.route("/products", methods=["GET"])
@admin_required
def list_products():
    page, per_page = validate_pagination(request.args)
    q = Product.query.filter_by(is_deleted=False)
    if search := request.args.get("q"):
        q = q.filter(Product.name.ilike(f"%{search}%") | Product.sku.ilike(f"%{search}%"))
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

# ─── ORDERS ───────────────────────────────────────
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

# ─── CATEGORIES ──────────────────────────────────
@admin_bp.route("/categories", methods=["GET"])
@admin_required
def list_categories():
    cats = Category.query.order_by(Category.sort_order, Category.name).all()
    return ok([c.to_dict() for c in cats])

@admin_bp.route("/categories", methods=["POST"])
@roles_required("super_admin", "manager")
def create_category():
    data = request.get_json(force=True)
    name = sanitise_text(data.get("name", ""))
    if not name: return err("name is required")
    cat = Category(name=name, slug=slugify(name),
                   description=sanitise_text(data.get("description", "")),
                   image_url=sanitise_text(data.get("image_url", "")),
                   is_active=data.get("is_active", True))
    db.session.add(cat); db.session.commit()
    return ok(cat.to_dict(), "Category created", 201)

@admin_bp.route("/categories/<cat_id>", methods=["PUT"])
@roles_required("super_admin", "manager")
def update_category(cat_id):
    cat = Category.query.get_or_404(cat_id)
    data = request.get_json(force=True)
    if "name" in data:
        cat.name = sanitise_text(data["name"]); cat.slug = slugify(data["name"])
    for f in ["description","image_url","is_active"]:
        if f in data: setattr(cat, f, data[f] if f!="is_active" else bool(data[f]))
    db.session.commit()
    return ok(cat.to_dict(), "Category updated")

@admin_bp.route("/categories/<cat_id>", methods=["DELETE"])
@roles_required("super_admin")
def delete_category(cat_id):
    cat = Category.query.get_or_404(cat_id)
    db.session.delete(cat); db.session.commit()
    return ok(message="Category deleted")

# ─── BRANDS ──────────────────────────────────────
@admin_bp.route("/brands", methods=["GET"])
@admin_required
def list_brands():
    return ok([b.to_dict() for b in Brand.query.order_by(Brand.name).all()])

@admin_bp.route("/brands", methods=["POST"])
@roles_required("super_admin", "manager")
def create_brand():
    data = request.get_json(force=True)
    name = sanitise_text(data.get("name", ""))
    if not name: return err("name is required")
    brand = Brand(name=name, slug=slugify(name),
                  description=sanitise_text(data.get("description","")),
                  logo_url=sanitise_text(data.get("logo_url","")),
                  is_active=data.get("is_active",True))
    db.session.add(brand); db.session.commit()
    return ok(brand.to_dict(), "Brand created", 201)

@admin_bp.route("/brands/<brand_id>", methods=["PUT"])
@roles_required("super_admin", "manager")
def update_brand(brand_id):
    brand = Brand.query.get_or_404(brand_id)
    data = request.get_json(force=True)
    if "name" in data: brand.name = sanitise_text(data["name"]); brand.slug = slugify(data["name"])
    for f in ["description","logo_url","is_active"]:
        if f in data: setattr(brand, f, data[f] if f!="is_active" else bool(data[f]))
    db.session.commit()
    return ok(brand.to_dict(), "Brand updated")

@admin_bp.route("/brands/<brand_id>", methods=["DELETE"])
@roles_required("super_admin")
def delete_brand(brand_id):
    db.session.delete(Brand.query.get_or_404(brand_id))
    db.session.commit()
    return ok(message="Brand deleted")

# ─── COUPONS ────────────────────────────────────
@admin_bp.route("/coupons", methods=["GET"])
@admin_required
def list_coupons():
    return ok({"coupons":[c.to_dict() for c in Coupon.query.order_by(Coupon.created_at.desc()).all()]})

@admin_bp.route("/coupons", methods=["POST"])
@roles_required("super_admin", "manager")
def create_coupon():
    data = request.get_json(force=True)
    code = sanitise_text(data.get("code","")).upper()
    if not code: return err("code is required")
    c = Coupon(code=code, discount_type=data["discount_type"],
               discount_value=float(data["discount_value"]),
               minimum_purchase=float(data.get("minimum_purchase",0)),
               maximum_discount=float(data["maximum_discount"]) if data.get("maximum_discount") else None,
               usage_limit=int(data["usage_limit"]) if data.get("usage_limit") else None,
               starts_at=datetime.now(timezone.utc),
               expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
               is_active=data.get("is_active",True))
    db.session.add(c); db.session.commit()
    return ok(c.to_dict(), "Coupon created", 201)

@admin_bp.route("/coupons/<coupon_id>", methods=["PUT"])
@roles_required("super_admin", "manager")
def update_coupon(coupon_id):
    c = Coupon.query.get_or_404(coupon_id)
    data = request.get_json(force=True)
    for f in ["discount_type","discount_value","minimum_purchase","maximum_discount","usage_limit","expires_at","is_active"]:
        if f in data: setattr(c, f, data[f])
    if "code" in data: c.code = sanitise_text(data["code"]).upper()
    db.session.commit()
    return ok(c.to_dict(), "Coupon updated")

@admin_bp.route("/coupons/<coupon_id>", methods=["DELETE"])
@roles_required("super_admin")
def delete_coupon(coupon_id):
    db.session.delete(Coupon.query.get_or_404(coupon_id))
    db.session.commit()
    return ok(message="Coupon deleted")

# ─── BANNERS ────────────────────────────────────
@admin_bp.route("/banners", methods=["GET"])
@admin_required
def list_banners():
    banners = Banner.query.order_by(Banner.sort_order, Banner.created_at.desc()).all()
    return ok([b.to_dict() for b in banners])

@admin_bp.route("/banners", methods=["POST"])
@roles_required("super_admin", "manager")
def create_banner():
    file = request.files.get('file') if request.files else None
    data = request.form if request.files else (request.get_json(force=True) or {})

    image_url = None
    try:
        if file and file.filename:
            image_url = convert_to_webp(file, upload_subfolder='banners')
        else:
            url = sanitise_text(data.get("image_url", ""))
            if not url:
                return err("Image file or image_url is required")
            image_url = convert_to_webp(url, upload_subfolder='banners')
    except (ValueError, RuntimeError) as exc:
        return err(str(exc))

    banner = Banner(
        title=sanitise_text(data.get("title", "")),
        subtitle=sanitise_text(data.get("subtitle", "")),
        image_url=image_url,
        link_url=sanitise_text(data.get("link_url", "")),
        position=sanitise_text(data.get("position", "hero")),
        is_active=str(data.get("is_active", "true")).lower() != "false",
    )
    db.session.add(banner)
    db.session.commit()
    return ok(banner.to_dict(), "Banner created", 201)

@admin_bp.route("/banners/<banner_id>", methods=["PUT"])
@roles_required("super_admin", "manager")
def update_banner(banner_id):
    banner = Banner.query.get_or_404(banner_id)
    file = request.files.get('file') if request.files else None
    data = request.form if request.files else (request.get_json(force=True) or {})

    if file and file.filename:
        try:
            banner.image_url = convert_to_webp(file, upload_subfolder='banners')
        except (ValueError, RuntimeError) as exc:
            return err(str(exc))
    elif data.get("image_url"):
        try:
            banner.image_url = convert_to_webp(data.get("image_url"), upload_subfolder='banners')
        except (ValueError, RuntimeError) as exc:
            return err(str(exc))

    for field in ["title", "subtitle", "link_url", "position"]:
        if field in data:
            setattr(banner, field, sanitise_text(data[field]))
    if "sort_order" in data:
        banner.sort_order = int(data.get("sort_order", 0))
    if "is_active" in data:
        banner.is_active = str(data.get("is_active")).lower() not in ("false", "0", "no")

    db.session.commit()
    return ok(banner.to_dict(), "Banner updated")

@admin_bp.route("/banners/<banner_id>", methods=["DELETE"])
@roles_required("super_admin")
def delete_banner(banner_id):
    db.session.delete(Banner.query.get_or_404(banner_id))
    db.session.commit()
    return ok(message="Banner deleted")

# ─── BLOG ──────────────────────────────────────
@admin_bp.route("/blog", methods=["GET"])
@admin_required
def list_blog_posts():
    return ok({"blog_posts":[p.to_dict(full=True) for p in BlogPost.query.order_by(BlogPost.created_at.desc()).all()]})

@admin_bp.route("/blog", methods=["POST"])
@roles_required("super_admin", "manager")
def create_blog_post():
    data = request.form if request.files else (request.get_json(force=True) or {})
    title = sanitise_text(data.get("title",""))
    if not title: return err("title is required")
    p = BlogPost(title=title, slug=slugify(title),
                 excerpt=sanitise_text(data.get("excerpt","")),
                 content=sanitise_html(data.get("content","")),
                 cover_image_url=sanitise_text(data.get("cover_image_url","")),
                 author_id=g.admin.id,
                 is_published=str(data.get("is_published","false")).lower()=="true",
                 meta_title=sanitise_text(data.get("meta_title","")),
                 meta_description=sanitise_text(data.get("meta_description","")))
    if p.is_published: p.published_at = datetime.now(timezone.utc)
    db.session.add(p); db.session.commit()
    return ok(p.to_dict(full=True), "Blog post created", 201)

@admin_bp.route("/blog/<post_id>", methods=["PUT"])
@roles_required("super_admin", "manager")
def update_blog_post(post_id):
    p = BlogPost.query.get_or_404(post_id)
    data = request.form if request.files else (request.get_json(force=True) or {})
    for f in ["title","excerpt","content","cover_image_url","is_published","meta_title","meta_description"]:
        if f in data: setattr(p, f, data[f] if f!="is_published" else str(data[f]).lower()=="true")
    if "title" in data: p.slug = slugify(data["title"])
    if p.is_published and not p.published_at: p.published_at = datetime.now(timezone.utc)
    db.session.commit()
    return ok(p.to_dict(full=True), "Blog post updated")

@admin_bp.route("/blog/<post_id>", methods=["DELETE"])
@roles_required("super_admin")
def delete_blog_post(post_id):
    db.session.delete(BlogPost.query.get_or_404(post_id))
    db.session.commit()
    return ok(message="Blog post deleted")

# ─── PAGES ──────────────────────────────────────
@admin_bp.route("/pages", methods=["GET"])
@admin_required
def list_pages():
    return ok([p.to_dict() for p in Page.query.order_by(Page.slug).all()])

@admin_bp.route("/pages", methods=["POST"])
@roles_required("super_admin", "manager")
def create_page():
    data = request.get_json(force=True)
    slug = slugify(sanitise_text(data.get("slug","")))
    title = sanitise_text(data.get("title",""))
    if not slug or not title: return err("slug and title are required")
    pg = Page(slug=slug, title=title, content=sanitise_html(data.get("content","")),
              is_published=data.get("is_published",True))
    db.session.add(pg); db.session.commit()
    return ok(pg.to_dict(), "Page created", 201)

@admin_bp.route("/pages/<page_id>", methods=["PUT"])
@roles_required("super_admin", "manager")
def update_page(page_id):
    pg = Page.query.get_or_404(page_id)
    data = request.get_json(force=True)
    for f in ["title","slug","content","is_published"]:
        if f in data: setattr(pg, f, data[f])
    db.session.commit()
    return ok(pg.to_dict(), "Page updated")

@admin_bp.route("/pages/<page_id>", methods=["DELETE"])
@roles_required("super_admin")
def delete_page(page_id):
    db.session.delete(Page.query.get_or_404(page_id))
    db.session.commit()
    return ok(message="Page deleted")

# ─── FAQS ───────────────────────────────────────
@admin_bp.route("/faqs", methods=["GET"])
@admin_required
def list_faqs():
    return ok([f.to_dict() for f in FAQ.query.order_by(FAQ.category, FAQ.sort_order).all()])

@admin_bp.route("/faqs", methods=["POST"])
@roles_required("super_admin", "manager")
def create_faq():
    data = request.get_json(force=True)
    if not data.get("question") or not data.get("answer"):
        return err("question and answer are required")
    faq = FAQ(question=sanitise_text(data["question"]), answer=sanitise_html(data["answer"]),
              category=sanitise_text(data.get("category","general")), is_active=data.get("is_active",True))
    db.session.add(faq); db.session.commit()
    return ok(faq.to_dict(), "FAQ created", 201)

@admin_bp.route("/faqs/<faq_id>", methods=["PUT"])
@roles_required("super_admin", "manager")
def update_faq(faq_id):
    faq = FAQ.query.get_or_404(faq_id)
    data = request.get_json(force=True)
    for f in ["question","answer","category","is_active"]:
        if f in data: setattr(faq, f, data[f])
    db.session.commit()
    return ok(faq.to_dict(), "FAQ updated")

@admin_bp.route("/faqs/<faq_id>", methods=["DELETE"])
@roles_required("super_admin")
def delete_faq(faq_id):
    db.session.delete(FAQ.query.get_or_404(faq_id))
    db.session.commit()
    return ok(message="FAQ deleted")

# ─── ADMINS ────────────────────────────────────
@admin_bp.route("/admins", methods=["GET"])
@roles_required("super_admin")
def list_admins():
    return ok([a.to_dict() for a in AdminUser.query.order_by(AdminUser.created_at.desc()).all()])

@admin_bp.route("/admins", methods=["POST"])
@roles_required("super_admin")
def create_admin():
    data = request.get_json(force=True)
    email = sanitise_text(data.get("email","")).lower().strip()
    password = data.get("password","")
    if not email or not password: return err("email and password are required")
    a = AdminUser(email=email, first_name=sanitise_text(data.get("first_name","")),
                  last_name=sanitise_text(data.get("last_name","")),
                  role=data.get("role","staff"), is_active=True)
    a.set_password(password)
    db.session.add(a); db.session.commit()
    return ok(a.to_dict(), "Admin created", 201)

@admin_bp.route("/admins/<admin_id>", methods=["PUT"])
@roles_required("super_admin")
def update_admin(admin_id):
    a = AdminUser.query.get_or_404(admin_id)
    data = request.get_json(force=True)
    for f in ["first_name","last_name","role","is_active"]:
        if f in data: setattr(a, f, data[f])
    if "password" in data: a.set_password(data["password"])
    db.session.commit()
    return ok(a.to_dict(), "Admin updated")

@admin_bp.route("/admins/<admin_id>", methods=["DELETE"])
@roles_required("super_admin")
def delete_admin(admin_id):
    if admin_id == g.admin.id: return err("You cannot delete your own account")
    db.session.delete(AdminUser.query.get_or_404(admin_id))
    db.session.commit()
    return ok(message="Admin deleted")

# ─── SITE SETTINGS ─────────────────────────────
@admin_bp.route("/settings", methods=["POST"])
@roles_required("super_admin", "admin")
def save_settings():
    file = request.files.get('file') if request.files else None
    data = request.form if request.files else (request.get_json(force=True) or {})

    if 'site_name' in data:
        SiteSettings.set('site_name', sanitise_text(data['site_name']))

    if file and file.filename:
        try:
            logo_url = convert_to_webp(file, upload_subfolder='site')
            SiteSettings.set('site_logo', logo_url)
        except (ValueError, RuntimeError) as exc:
            return err(str(exc) or "Invalid logo file")
    elif 'site_logo' in data:
        logo_url = sanitise_text(data['site_logo'])
        SiteSettings.set('site_logo', logo_url)

    return ok(message="Settings saved")

# ─── HOMEPAGE CONTENT ──────────────────────────
@admin_bp.route("/homepage-items", methods=["GET"])
@admin_required
def list_homepage_items():
    section = request.args.get("section")
    if not section:
        return err("section is required")
    raw = SiteSettings.get(f"homepage_{section}", "[]")
    try:
        items = json.loads(raw)
    except Exception:
        items = []
    return ok(items)

@admin_bp.route("/homepage-items", methods=["POST"])
@roles_required("super_admin", "admin")
def add_homepage_item():
    file = request.files.get('file')
    section = request.form.get('section')
    if not section:
        return err("section is required")

    raw = SiteSettings.get(f"homepage_{section}", "[]")
    try:
        items = json.loads(raw)
    except Exception:
        items = []

    image_url = None
    if file and file.filename:
        try:
            image_url = convert_to_webp(file, upload_subfolder=f"homepage/{section}")
        except (ValueError, RuntimeError) as exc:
            return err(str(exc))
    else:
        image_url = sanitise_text(request.form.get("image_url", ""))

    if section == "lookbook":
        item = {"url": image_url, "title": request.form.get("title", ""), "label": request.form.get("label", "")}
    elif section == "designers":
        item = {"image": image_url, "name": request.form.get("name", ""), "brand": request.form.get("brand", ""), "origin": request.form.get("origin", "")}
    elif section == "pillars":
        item = {"icon": request.form.get("icon", ""), "title": request.form.get("title", ""), "text": request.form.get("text", "")}
    elif section == "testimonials":
        item = {"stars": request.form.get("stars", ""), "quote": request.form.get("quote", ""), "name": request.form.get("name", ""), "role": request.form.get("role", ""), "initial": request.form.get("name", "")[0].upper() if request.form.get("name") else ""}
    else:
        return err("Invalid section")

    items.append(item)
    SiteSettings.set(f"homepage_{section}", json.dumps(items, ensure_ascii=False))
    return ok(message="Item added", status=201)

@admin_bp.route("/homepage-items", methods=["DELETE"])
@roles_required("super_admin", "admin")
def delete_homepage_item():
    section = request.args.get("section")
    index = request.args.get("index", -1, type=int)
    if not section or index < 0:
        return err("section and index are required")
    raw = SiteSettings.get(f"homepage_{section}", "[]")
    try:
        items = json.loads(raw)
    except Exception:
        items = []
    if 0 <= index < len(items):
        items.pop(index)
        SiteSettings.set(f"homepage_{section}", json.dumps(items, ensure_ascii=False))
    return ok(message="Deleted")

@admin_bp.route("/homepage-items/press", methods=["POST"])
@roles_required("super_admin", "admin")
def save_press():
    data = request.get_json(force=True)
    logos = data.get("logos", "")
    logo_list = [l.strip() for l in logos.split("\n") if l.strip()]
    SiteSettings.set("homepage_press", json.dumps(logo_list, ensure_ascii=False))
    return ok(message="Press logos saved")

@admin_bp.route("/homepage-items/editorial", methods=["POST"])
@roles_required("super_admin", "admin")
def save_editorial():
    file = request.files.get('file')
    data = request.form if request.files else (request.get_json(force=True) or {})

    if file and file.filename:
        try:
            image_url = convert_to_webp(file, upload_subfolder="homepage/editorial")
            SiteSettings.set("editorial_image", image_url)
        except (ValueError, RuntimeError) as exc:
            return err(str(exc))
    elif "image_url" in data:
        SiteSettings.set("editorial_image", sanitise_text(data["image_url"]))

    for field in ["eyebrow", "title", "text", "season"]:
        if field in data:
            SiteSettings.set(f"editorial_{field}", sanitise_text(data[field]))

    return ok(message="Editorial saved")