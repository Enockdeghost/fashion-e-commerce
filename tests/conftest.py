import os
import sys
import pytest
from app.extensions import db as _db
from app.models import (
    Product, ProductVariant, ProductImage,
    Category, Brand, Collection, Tag,
    Cart, CartItem, Coupon, ShippingRate, AdminUser,
    Order, Payment, Wishlist,
)
from app import create_app

# Set test config environment
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ["FLASK_CONFIG"] = "testing"


@pytest.fixture(scope="session")
def app():
    """Create app for testing with in‑memory SQLite."""
    app = create_app("testing")
    with app.app_context():
        _db.create_all()
    yield app
    with app.app_context():
        _db.drop_all()


@pytest.fixture
def db(app):
    """Return the SQLAlchemy database object."""
    return _db


@pytest.fixture
def client(app):
    """Test client for making requests."""
    return app.test_client()


@pytest.fixture
def session_token(client):
    """Generate a guest session token for cart/wishlist tests."""
    import secrets
    return secrets.token_urlsafe(32)


@pytest.fixture
def admin_user(db):
    """Create a test admin."""
    admin = AdminUser(
        email="admin@test.com",
        first_name="Admin",
        last_name="User",
        role="super_admin",
        is_active=True,
    )
    admin.set_password("password123")
    db.session.add(admin)
    db.session.commit()
    return admin


@pytest.fixture
def admin_token(client, admin_user):
    """Obtain a JWT token for the admin."""
    resp = client.post("/api/admin/login", json={
        "email": "admin@test.com",
        "password": "password123"
    })
    return resp.get_json()["data"]["access_token"]


@pytest.fixture
def sample_category(db):
    cat = Category(name="Dresses", slug="dresses")
    db.session.add(cat)
    db.session.commit()
    return cat


@pytest.fixture
def sample_brand(db):
    brand = Brand(name="Luxé", slug="luxe")
    db.session.add(brand)
    db.session.commit()
    return brand


@pytest.fixture
def sample_product(db, sample_category, sample_brand):
    """Create a product with one variant and primary image."""
    product = Product(
        name="Evening Gown",
        slug="evening-gown",
        base_price=250000,
        category_id=sample_category.id,
        brand_id=sample_brand.id,
        is_active=True,
    )
    db.session.add(product)
    db.session.flush()

    variant = ProductVariant(
        product_id=product.id,
        sku="SKU-EVE-BLACK-M",
        size="M",
        color="Black",
        stock=10,
    )
    db.session.add(variant)

    image = ProductImage(
        product_id=product.id,
        url="https://example.com/image.jpg",
        thumbnail_url="https://example.com/thumb.jpg",
        is_primary=True,
    )
    db.session.add(image)

    db.session.commit()
    return product


@pytest.fixture
def sample_coupon(db):
    coupon = Coupon(
        code="LUXE10",
        discount_type="percentage",
        discount_value=10,
        minimum_purchase=100000,
        is_active=True,
    )
    db.session.add(coupon)
    db.session.commit()
    return coupon


@pytest.fixture
def cart_with_item(client, session_token, sample_product):
    """Create a cart with one item."""
    payload = {
        "token": session_token,
        "product_id": sample_product.id,
        "variant_id": sample_product.variants[0].id,
        "quantity": 2,
    }
    client.post("/api/cart/add", json=payload)
    return session_token