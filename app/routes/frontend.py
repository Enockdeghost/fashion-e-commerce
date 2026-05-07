from flask import Blueprint, render_template, request, redirect, url_for
from datetime import datetime, timezone
from functools import wraps
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from app.models import Product, Category, Brand, Banner, BlogPost, Page, AdminUser

frontend_bp = Blueprint('frontend', __name__)

def _now():
    return datetime.now(timezone.utc)

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            verify_jwt_in_request(locations=["cookies"])
            admin_id = get_jwt_identity()
            admin = AdminUser.query.get(admin_id)
            if not admin or not admin.is_active:
                raise Exception("Not authorised")
        except Exception:
            return redirect(url_for('frontend.admin_login'))
        return f(*args, **kwargs)
    return decorated

@frontend_bp.route('/')
def index():
    banners = Banner.query.filter_by(is_active=True).all()
    categories = Category.query.filter_by(is_active=True, parent_id=None).all()
    products = Product.query.filter_by(is_active=True, is_deleted=False, is_featured=True).limit(6).all()
    return render_template('index.html', banners=banners, categories=categories, products=products, now=_now())

@frontend_bp.route('/login', methods=['GET'])
def login():
    return render_template('auth/login.html', now=_now())

@frontend_bp.route('/register', methods=['GET'])
def register():
    return render_template('auth/register.html', now=_now())

@frontend_bp.route('/products')
def products():
    cat_slug = request.args.get('category')
    brand_slug = request.args.get('brand')
    categories = Category.query.filter_by(is_active=True, parent_id=None).all()
    brands = Brand.query.filter_by(is_active=True).all()
    category_name = None
    if cat_slug:
        cat = Category.query.filter((Category.id == cat_slug) | (Category.slug == cat_slug)).first()
        if cat:
            category_name = cat.name
    product_query = Product.query.filter_by(is_active=True, is_deleted=False)
    if cat_slug:
        product_query = product_query.filter(Product.category.has(slug=cat_slug))
    if brand_slug:
        product_query = product_query.filter(Product.brand.has(slug=brand_slug))
    products_list = product_query.order_by(Product.created_at.desc()).limit(24).all()
    return render_template('products/list.html', products=products_list, categories=categories, brands=brands, category_name=category_name, now=_now())

@frontend_bp.route('/products/<product_slug>')
def product_detail(product_slug):
    product = Product.query.filter(
        (Product.slug == product_slug) | (Product.id == product_slug),
        Product.is_deleted == False,
        Product.is_active == True
    ).first_or_404()
    return render_template('products/detail.html', product=product, now=_now())

@frontend_bp.route('/category/<slug>')
def category(slug):
    cat = Category.query.filter((Category.slug == slug) | (Category.id == slug)).first_or_404()
    products = Product.query.filter_by(category_id=cat.id, is_active=True, is_deleted=False).order_by(Product.created_at.desc()).limit(24).all()
    return render_template('products/category.html', category=cat, products=products, now=_now())

@frontend_bp.route('/cart')
def cart():
    return render_template('cart/view.html', now=_now())

@frontend_bp.route('/checkout')
def checkout():
    return render_template('checkout/view.html', now=_now())

@frontend_bp.route('/wishlist')
def wishlist():
    return render_template('wishlist/view.html', now=_now())

@frontend_bp.route('/lookbook')
def lookbook():
    return render_template('lookbook/view.html', now=_now())

@frontend_bp.route('/dashboard')
def dashboard():
    return render_template('user/dashboard.html', now=_now())

@frontend_bp.route('/orders')
def orders():
    return render_template('user/orders.html', now=_now())

@frontend_bp.route('/order/<order_number>')
def order_detail(order_number):
    return render_template('user/order_detail.html', order_number=order_number, now=_now())

@frontend_bp.route('/page/<slug>')
def cms_page(slug):
    page = Page.query.filter_by(slug=slug, is_published=True).first_or_404()
    return render_template('cms/page.html', page=page, now=_now())

@frontend_bp.route('/blog')
def blog():
    posts = BlogPost.query.filter_by(is_published=True).order_by(BlogPost.published_at.desc()).all()
    return render_template('blog/list.html', posts=posts, now=_now())

@frontend_bp.route('/blog/<slug>')
def blog_post(slug):
    post = BlogPost.query.filter_by(slug=slug, is_published=True).first_or_404()
    return render_template('blog/post.html', post=post, now=_now())

@frontend_bp.route('/search')
def search():
    query = request.args.get('q', '')
    return render_template('search/results.html', query=query, now=_now())

@frontend_bp.route('/admin')
def admin_login():
    return render_template('admin/login.html', now=_now())

@frontend_bp.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    return render_template('admin/dashboard.html', now=_now())

@frontend_bp.route('/admin/products')
@admin_required
def admin_products():
    return render_template('admin/products.html', now=_now())

@frontend_bp.route('/admin/products/new', methods=['GET'])
@admin_required
def admin_product_new():
    return render_template('admin/product_form.html', product=None, now=_now())

@frontend_bp.route('/admin/products/<product_id>/edit', methods=['GET'])
@admin_required
def admin_product_edit(product_id):
    product = Product.query.get_or_404(product_id)
    return render_template('admin/product_form.html', product=product, now=_now())

@frontend_bp.route('/admin/orders')
@admin_required
def admin_orders():
    return render_template('admin/orders.html', now=_now())

@frontend_bp.route('/admin/categories')
@admin_required
def admin_categories():
    return render_template('admin/categories.html', now=_now())

@frontend_bp.route('/admin/categories/new')
@admin_required
def admin_category_new():
    return render_template('admin/category_form.html', category=None, now=_now())

@frontend_bp.route('/admin/categories/<category_id>/edit')
@admin_required
def admin_category_edit(category_id):
    category = Category.query.get_or_404(category_id)
    return render_template('admin/category_form.html', category=category, now=_now())

@frontend_bp.route('/admin/brands')
@admin_required
def admin_brands():
    return render_template('admin/brands.html', now=_now())

@frontend_bp.route('/admin/brands/new')
@admin_required
def admin_brand_new():
    return render_template('admin/brand_form.html', brand=None, now=_now())

@frontend_bp.route('/admin/brands/<brand_id>/edit')
@admin_required
def admin_brand_edit(brand_id):
    brand = Brand.query.get_or_404(brand_id)
    return render_template('admin/brand_form.html', brand=brand, now=_now())

@frontend_bp.route('/admin/coupons')
@admin_required
def admin_coupons():
    return render_template('admin/coupons.html', now=_now())

@frontend_bp.route('/admin/banners')
@admin_required
def admin_banners():
    return render_template('admin/banners.html', now=_now())

@frontend_bp.route('/admin/banners/new')
@admin_required
def admin_banner_new():
    return render_template('admin/banner_form.html', banner=None, now=_now())

@frontend_bp.route('/admin/banners/<banner_id>/edit')
@admin_required
def admin_banner_edit(banner_id):
    banner = Banner.query.get_or_404(banner_id)
    return render_template('admin/banner_form.html', banner=banner, now=_now())

@frontend_bp.route('/admin/blog')
@admin_required
def admin_blog_list():
    return render_template('admin/blog_list.html', now=_now())

@frontend_bp.route('/admin/blog/new')
@admin_required
def admin_blog_new():
    return render_template('admin/blog_form.html', post=None, now=_now())

@frontend_bp.route('/admin/blog/<post_id>/edit')
@admin_required
def admin_blog_edit(post_id):
    post = BlogPost.query.get_or_404(post_id)
    return render_template('admin/blog_form.html', post=post, now=_now())

@frontend_bp.route('/admin/pages')
@admin_required
def admin_pages():
    return render_template('admin/pages.html', now=_now())

@frontend_bp.route('/admin/admins')
@admin_required
def admin_admins():
    return render_template('admin/admins.html', now=_now())