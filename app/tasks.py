from app.models import Product
from elasticsearch import Elasticsearch
from flask import current_app
import requests
from celery import Celery
from flask import current_app
from . import create_app

celery = Celery(__name__)

# Configure from Flask config
celery.config_from_object("app.config:Config")


def init_celery(app=None):
    """Attach Flask app context to Celery tasks."""
    app = app or create_app()
    celery.conf.update(
        broker_url=app.config["CELERY_BROKER_URL"],
        result_backend=app.config["CELERY_RESULT_BACKEND"],
    )

    class ContextTask(celery.Task):
        abstract = True

        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery


# ── Email Tasks 

@celery.task(name="send_email")
def send_email(to_email: str, subject: str, html_body: str, text_body: str = ""):
    """Send an email via SendGrid (asynchronous)."""
    from app.services.email_service import _send  # reuse sync helper
    _send(to_email, subject, html_body)


@celery.task(name="send_order_confirmation")
def send_order_confirmation(order_id: str):
    """Send order confirmation email."""
    from app.models import Order
    from app.services.email_service import send_order_confirmation as _sync_send
    order = Order.query.get(order_id)
    if order:
        _sync_send(order)


@celery.task(name="send_admin_low_stock_alert")
def send_admin_low_stock_alert(variant_id: str):
    """Low‑stock notification to admin email."""
    from app.models import ProductVariant
    from flask import current_app
    from app.services.email_service import send_admin_low_stock_alert as _sync_alert
    variant = ProductVariant.query.get(variant_id)
    if variant and variant.is_low_stock:
        admin_email = current_app.config.get("SUPER_ADMIN_EMAIL")
        if admin_email:
            _sync_alert(variant, admin_email)


# ── Maintenance Tasks 
@celery.task(name="clean_expired_carts")
def clean_expired_carts():
    """Delete expired guest carts and save them as abandoned."""
    from datetime import datetime, timezone
    from app import db
    from app.models import Cart, AbandonedCart

    expired = Cart.query.filter(Cart.expires_at < datetime.now(timezone.utc)).all()
    for cart in expired:
        if cart.items.count():
            # Snapshot cart for analytics
            ac = AbandonedCart(
                session_token=cart.session_token,
                items_snapshot=[i.to_dict() for i in cart.items],
                subtotal=cart.subtotal,
            )
            db.session.add(ac)
        db.session.delete(cart)
    db.session.commit()
    return len(expired)


@celery.task(name="release_reserved_stock")
def release_reserved_stock():
    """Release reserved stock from expired carts."""
    from datetime import datetime, timezone
    from app import db
    from app.models import Cart

    expired = Cart.query.filter(Cart.expires_at < datetime.now(timezone.utc)).all()
    for cart in expired:
        for item in cart.items:
            if item.variant:
                item.variant.reserved_stock = max(0, item.variant.reserved_stock - item.quantity)
        db.session.delete(cart)
    db.session.commit()
    return len(expired)


# ── Indexing Task (optional)

@celery.task(name="reindex_products")
def reindex_products():
    """Sync all active products to Elasticsearch."""
    try:
        es = Elasticsearch([current_app.config["ELASTICSEARCH_URL"]])
        products = Product.query.filter_by(is_active=True, is_deleted=False).all()
        for p in products:
            doc = {
                "id": p.id,
                "name": p.name,
                "slug": p.slug,
                "description": p.description,
                "base_price": float(p.base_price),
                "primary_image": p.primary_image,
                "category": p.category.name if p.category else None,
                "brand": p.brand.name if p.brand else None,
                "tags": [t.name for t in p.tags],
            }
            es.index(index="products", id=p.id, body=doc)
        return len(products)
    except Exception as e:
        return str(e)