import secrets
from flask import Blueprint, request
from app.extensions import db
from app.models import Wishlist, Product, ProductVariant
from app.utils.security import ok, err

wishlist_bp = Blueprint("wishlist", __name__, url_prefix="/wishlist")


def _require_token():
    token = (
        request.headers.get("X-Cart-Token")
        or request.args.get("token")
        or (request.get_json(silent=True) or {}).get("token")
    )
    if not token:
        token = secrets.token_urlsafe(32)
    return token


@wishlist_bp.route("", methods=["GET"])
def get_wishlist():
    token = _require_token()
    items = (
        Wishlist.query
        .filter_by(session_token=token)
        .order_by(Wishlist.created_at.desc())
        .all()
    )
    return ok({
        "wishlist": [item.to_dict() for item in items],
        "token": token,
    })


@wishlist_bp.route("", methods=["POST"])
def add_to_wishlist():
    data = request.get_json(force=True)
    token = data.get("token") or _require_token()
    product_id = data.get("product_id")
    variant_id = data.get("variant_id")  # optional

    if not product_id:
        return err("product_id is required")

    product = Product.query.filter_by(id=product_id, is_active=True, is_deleted=False).first()
    if not product:
        return err("Product not found", 404)

    # Check for duplicate
    existing = Wishlist.query.filter_by(
        session_token=token, product_id=product_id, variant_id=variant_id
    ).first()
    if existing:
        return ok({"wishlist": existing.to_dict(), "token": token}, "Item already in wishlist")

    entry = Wishlist(
        session_token=token,
        product_id=product_id,
        variant_id=variant_id,
    )
    db.session.add(entry)
    db.session.commit()

    return ok({"wishlist": entry.to_dict(), "token": token}, "Added to wishlist", 201)


@wishlist_bp.route("/<item_id>", methods=["DELETE"])
def remove_from_wishlist(item_id):
    token = request.headers.get("X-Cart-Token") or request.args.get("token")
    if not token:
        return err("Token required")

    entry = Wishlist.query.filter_by(id=item_id, session_token=token).first()
    if not entry:
        return err("Item not found in your wishlist", 404)

    db.session.delete(entry)
    db.session.commit()
    return ok(message="Removed from wishlist")