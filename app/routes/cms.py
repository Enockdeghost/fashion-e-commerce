from flask import Blueprint, request
from app.models import Banner, BlogPost, Page, FAQ
from app.utils.security import ok, err, validate_pagination

cms_bp = Blueprint("cms", __name__, url_prefix="/cms")


# ── Banners 

@cms_bp.route("/banners", methods=["GET"])
def get_banners():
    position = request.args.get("position", "homepage_hero")
    banners = (
        Banner.query
        .filter_by(is_active=True, position=position)
        .order_by(Banner.sort_order)
        .all()
    )
    return ok([b.to_dict() for b in banners])


# ── Blog 
@cms_bp.route("/blog", methods=["GET"])
def get_blog_posts():
    page, per_page = validate_pagination(request.args)
    q = (
        BlogPost.query
        .filter_by(is_published=True)
        .order_by(BlogPost.published_at.desc())
    )
    paginated = q.paginate(page=page, per_page=per_page, error_out=False)
    return ok({
        "posts": [p.to_dict() for p in paginated.items],
        "pagination": {"page": page, "per_page": per_page, "total": paginated.total},
    })


@cms_bp.route("/blog/<slug>", methods=["GET"])
def get_blog_post(slug):
    post = BlogPost.query.filter_by(slug=slug, is_published=True).first_or_404()
    return ok(post.to_dict(full=True))


# ── Pages 

@cms_bp.route("/pages/<slug>", methods=["GET"])
def get_page(slug):
    page = Page.query.filter_by(slug=slug, is_published=True).first_or_404()
    return ok(page.to_dict())


# ── FAQs 

@cms_bp.route("/faqs", methods=["GET"])
def get_faqs():
    category = request.args.get("category")
    q = FAQ.query.filter_by(is_active=True).order_by(FAQ.sort_order)
    if category:
        q = q.filter(FAQ.category == category)
    all_faqs = q.all()
    return ok([f.to_dict() for f in all_faqs])