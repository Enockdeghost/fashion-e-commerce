"""
Fred Vunjabei – database seeder.
Run once to populate the store with sample data.
Usage:  flask shell
        exec(open('app/seed.py').read())
"""
from app.models import (
    Category, Brand, Product, ProductImage, ProductVariant,
    AdminUser, BlogPost, Page,
)
from app.extensions import db
from datetime import datetime, timezone

_now = datetime.now(timezone.utc)

# ── 1. Brand ────────────────────────────────────────────────────────────────
brand = Brand.query.filter_by(slug="fred-vunjabei").first()
if not brand:
    brand = Brand(
        name="Fred Vunjabei",
        slug="fred-vunjabei",
        description="Tanzanian luxury fashion house.",
        logo_url="https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=200&q=85",
    )
    db.session.add(brand)
    db.session.flush()

# ── 2. Categories ──────────────────────────────────────────────────────────
cat_data = [
    {"name": "Womenswear", "slug": "womenswear",
     "image": "https://images.unsplash.com/photo-1469334031218-e382a71b716b?w=600&q=85"},
    {"name": "Menswear", "slug": "menswear",
     "image": "https://images.unsplash.com/photo-1487222477894-8943e31ef7b2?w=600&q=85"},
    {"name": "Jeans", "slug": "jeans",
     "image": "https://images.unsplash.com/photo-1543163521-1bf539c55dd2?w=600&q=85"},
    {"name": "T‑Shirts", "slug": "tshirts",
     "image": "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=600&q=85"},
    {"name": "Sport", "slug": "sport",
     "image": "https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=600&q=85"},
    {"name": "Accessories", "slug": "accessories",
     "image": "https://images.unsplash.com/photo-1611601322175-ef8ec8c78e14?w=600&q=85"},
]
categories = {}
for cd in cat_data:
    cat = Category.query.filter_by(slug=cd["slug"]).first()
    if not cat:
        cat = Category(
            name=cd["name"],
            slug=cd["slug"],
            image_url=cd["image"],
            is_active=True,
        )
        db.session.add(cat)
        db.session.flush()
    categories[cd["slug"]] = cat

# ── 3. Products ────────────────────────────────────────────────────────────
product_data = [
    {"name": "Silk Evening Gown", "slug": "silk-evening-gown", "base_price": 345000,
     "compare_price": 420000, "category": "womenswear",
     "desc": "Ethereal silk gown with hand‑finished hem.",
     "images": ["https://images.unsplash.com/photo-1539109136881-3be0616acf4b?w=900&q=85",
                "https://images.unsplash.com/photo-1509631179647-0177331693ae?w=900&q=85"],
     "size": "M", "color": "Black", "stock": 5},
    {"name": "Tailored Wool Blazer", "slug": "tailored-wool-blazer", "base_price": 210000,
     "category": "menswear",
     "desc": "Double‑breasted blazer in superfine wool.",
     "images": ["https://images.unsplash.com/photo-1591047139829-d91aecb6caea?w=900&q=85"],
     "size": "L", "color": "Navy", "stock": 8},
    {"name": "Slim Blue Jeans", "slug": "slim-blue-jeans", "base_price": 95000,
     "category": "jeans",
     "desc": "Japanese selvedge denim, slim fit.",
     "images": ["https://images.unsplash.com/photo-1543163521-1bf539c55dd2?w=900&q=85"],
     "size": "32", "color": "Blue", "stock": 20},
    {"name": "Classic White Tee", "slug": "classic-white-tee", "base_price": 45000,
     "category": "tshirts",
     "desc": "Organic cotton, tailored silhouette.",
     "images": ["https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=900&q=85"],
     "size": "M", "color": "White", "stock": 30},
    {"name": "Performance Jersey", "slug": "performance-jersey", "base_price": 120000,
     "category": "sport",
     "desc": "Moisture‑wicking, four‑way stretch.",
     "images": ["https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=900&q=85"],
     "size": "L", "color": "Green", "stock": 12},
    {"name": "Leather Tote Bag", "slug": "leather-tote-bag", "base_price": 180000,
     "compare_price": 220000, "category": "accessories",
     "desc": "Full‑grain Tanzanian leather, brass hardware.",
     "images": ["https://images.unsplash.com/photo-1611601322175-ef8ec8c78e14?w=900&q=85"],
     "size": None, "color": "Tan", "stock": 6},
    {"name": "Pleated Silk Skirt", "slug": "pleated-silk-skirt", "base_price": 260000,
     "category": "womenswear",
     "desc": "Midi length, fluid silk georgette.",
     "images": ["https://images.unsplash.com/photo-1495385794356-15371f348c31?w=900&q=85"],
     "size": "S", "color": "Ivory", "stock": 4},
    {"name": "Cashmere Knit Sweater", "slug": "cashmere-knit-sweater", "base_price": 290000,
     "category": "menswear",
     "desc": "Ribbed crewneck in pure Mongolian cashmere.",
     "images": ["https://images.unsplash.com/photo-1487222477894-8943e31ef7b2?w=900&q=85"],
     "size": "XL", "color": "Grey", "stock": 7},
    {"name": "Denim Jacket", "slug": "denim-jacket", "base_price": 135000,
     "category": "jeans",
     "desc": "Oversized vintage wash denim jacket.",
     "images": ["https://images.unsplash.com/photo-1543163521-1bf539c55dd2?w=900&q=85"],
     "size": "M", "color": "Light Blue", "stock": 10},
    {"name": "Graphic Print Tee", "slug": "graphic-print-tee", "base_price": 55000,
     "category": "tshirts",
     "desc": "Limited edition Fred Vunjabei artwork.",
     "images": ["https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=900&q=85"],
     "size": "S", "color": "Black", "stock": 15},
    {"name": "Training Shorts", "slug": "training-shorts", "base_price": 80000,
     "category": "sport",
     "desc": "Lightweight, breathable, quick‑dry.",
     "images": ["https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=900&q=85"],
     "size": "L", "color": "Black", "stock": 18},
    {"name": "Silk Pocket Square", "slug": "silk-pocket-square", "base_price": 35000,
     "category": "accessories",
     "desc": "Hand‑rolled edges, signature monogram.",
     "images": ["https://images.unsplash.com/photo-1611601322175-ef8ec8c78e14?w=900&q=85"],
     "size": None, "color": "Burgundy", "stock": 25},
]

for pd in product_data:
    p = Product.query.filter_by(slug=pd["slug"]).first()
    if not p:
        p = Product(
            name=pd["name"],
            slug=pd["slug"],
            base_price=pd["base_price"],
            compare_price=pd.get("compare_price"),
            description=pd["desc"],
            category_id=categories[pd["category"]].id,
            brand_id=brand.id,
            is_active=True,
            is_featured=True,
            is_new_arrival=True,
        )
        db.session.add(p)
        db.session.flush()

        # variant
        v = ProductVariant(
            product_id=p.id,
            size=pd["size"],
            color=pd["color"],
            stock=pd["stock"],
            sku=f"SKU-{pd['slug'][:4].upper()}-{pd.get('size','OS')[:4]}",
        )
        db.session.add(v)
        db.session.flush()

        # images
        for idx, img_url in enumerate(pd["images"]):
            img = ProductImage(
                product_id=p.id,
                url=img_url,
                is_primary=(idx == 0),
                alt_text=pd["name"],
                sort_order=idx,
            )
            db.session.add(img)

# ── 4. Admin user ──────────────────────────────────────────────────────────
if not AdminUser.query.filter_by(email="admin@fredvunjabei.com").first():
    admin = AdminUser(
        email="admin@fredvunjabei.com",
        first_name="Fred",
        last_name="Admin",
        role="super_admin",
        is_active=True,
    )
    admin.set_password("admin123")
    db.session.add(admin)
    print("✓ Admin created: admin@fredvunjabei.com / admin123")

# ── 5. Blog posts ──────────────────────────────────────────────────────────
if not BlogPost.query.first():
    bp1 = BlogPost(
        title="The Art of Tanzanian Silk",
        slug="art-of-tanzanian-silk",
        excerpt="Discover how our artisans transform raw silk into gowns of ethereal beauty.",
        content="<p>Deep in the heart of Tanzania, our silk artisans ...</p>",
        cover_image_url="https://images.unsplash.com/photo-1539109136881-3be0616acf4b?w=800&q=85",
        is_published=True,
        published_at=_now,
    )
    bp2 = BlogPost(
        title="Behind the Seams: Spring 2026",
        slug="behind-the-seams-ss26",
        excerpt="Go behind the scenes of our most ambitious collection yet.",
        content="<p>The creative direction for Spring 2026 was ...</p>",
        cover_image_url="https://images.unsplash.com/photo-1509631179647-0177331693ae?w=800&q=85",
        is_published=True,
        published_at=_now,
    )
    db.session.add_all([bp1, bp2])

# ── 6. CMS pages ──────────────────────────────────────────────────────────
if not Page.query.first():
    p1 = Page(
        slug="about",
        title="About Fred Vunjabei",
        content="<p>Founded in 2025, Fred Vunjabei is a Tanzanian luxury fashion house ...</p>",
        is_published=True,
    )
    p2 = Page(
        slug="terms",
        title="Terms & Conditions",
        content="<p>Welcome to Fred Vunjabei. By accessing this site ...</p>",
        is_published=True,
    )
    db.session.add_all([p1, p2])

# ── 7. Commit everything ──────────────────────────────────────────────────
db.session.commit()
print("✓ Seeder complete — 6 categories, 12 products, 2 blog posts, 2 pages added.")