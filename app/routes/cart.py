
import secrets
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify
from app.extensions import db
from app.models import Cart, CartItem, Product, ProductVariant, Coupon
from app.utils.security import ok, err, validate_pagination

cart_bp = Blueprint("cart", __name__, url_prefix="/cart")


def _get_or_create_cart(token: str) -> Cart:
    """Return existing non-expired cart or create a new one."""
    from flask import current_app
    cart = Cart.query.filter_by(session_token=token).first()
    if cart and cart.is_expired:
        # Save as abandoned cart for analytics
        _record_abandoned(cart)
        db.session.delete(cart)
        db.session.flush()
        cart = None
    if not cart:
        expiry = datetime.now(timezone.utc) + timedelta(
            hours=current_app.config.get("CART_EXPIRY_HOURS", 72)
        )
        cart = Cart(session_token=token, expires_at=expiry)
        db.session.add(cart)
        db.session.flush()
    return cart


def _record_abandoned(cart: Cart):
    try:
        from app.models import AbandonedCart
        ac = AbandonedCart(
            session_token=cart.session_token,
            items_snapshot=[i.to_dict() for i in cart.items],
            subtotal=cart.subtotal,
        )
        db.session.add(ac)
    except Exception:
        pass


def _require_token():
    token = (
        request.headers.get("X-Cart-Token")
        or request.args.get("token")
        or (request.get_json(silent=True) or {}).get("token")
    )
    if not token:
        token = secrets.token_urlsafe(32)
    return token


# ─── GET CART 

@cart_bp.route("", methods=["GET"])
def get_cart():
    token = _require_token()
    cart = Cart.query.filter_by(session_token=token).first()
    if not cart or cart.is_expired:
        return ok({"cart": None, "token": token})
    return ok({"cart": cart.to_dict(), "token": token})


# ─── ADD ITEM 

@cart_bp.route("/add", methods=["POST"])
def add_item():
    data = request.get_json(force=True)
    token = data.get("token") or request.headers.get("X-Cart-Token") or secrets.token_urlsafe(32)

    product_id = data.get("product_id")
    variant_id = data.get("variant_id")
    quantity = int(data.get("quantity", 1))

    if not product_id:
        return err("product_id is required")
    if quantity < 1:
        return err("Quantity must be at least 1")

    product = Product.query.filter_by(id=product_id, is_active=True, is_deleted=False).first()
    if not product:
        return err("Product not found", 404)

    # Validate variant if provided
    variant = None
    if variant_id:
        variant = ProductVariant.query.filter_by(id=variant_id, product_id=product_id, is_active=True).first()
        if not variant:
            return err("Variant not found", 404)
        if variant.available_stock < quantity:
            return err(f"Only {variant.available_stock} units available")

    # Determine unit price
    unit_price = float(variant.price) if (variant and variant.price) else float(product.base_price)

    cart = _get_or_create_cart(token)

    # Check if item already in cart
    existing = CartItem.query.filter_by(
        cart_id=cart.id, product_id=product_id, variant_id=variant_id
    ).first()

    if existing:
        new_qty = existing.quantity + quantity
        # Check stock
        if variant and variant.available_stock < new_qty:
            return err(f"Only {variant.available_stock} units available")
        existing.quantity = new_qty
    else:
        item = CartItem(
            cart_id=cart.id,
            product_id=product_id,
            variant_id=variant_id,
            quantity=quantity,
            unit_price=unit_price,
        )
        db.session.add(item)

    db.session.commit()
    return ok({"cart": cart.to_dict(), "token": token}, "Item added to cart")


# ─── UPDATE QUANTITY 

@cart_bp.route("/update", methods=["PUT"])
def update_item():
    data = request.get_json(force=True)
    token = data.get("token") or request.headers.get("X-Cart-Token")
    item_id = data.get("item_id")
    quantity = int(data.get("quantity", 1))

    if not token:
        return err("Cart token required")
    cart = Cart.query.filter_by(session_token=token).first()
    if not cart:
        return err("Cart not found", 404)

    item = CartItem.query.filter_by(id=item_id, cart_id=cart.id).first_or_404()

    if quantity <= 0:
        db.session.delete(item)
    else:
        if item.variant:
            if item.variant.available_stock < quantity:
                return err(f"Only {item.variant.available_stock} units available")
        item.quantity = quantity

    db.session.commit()
    return ok({"cart": cart.to_dict()}, "Cart updated")


# ─── REMOVE ITEM 
@cart_bp.route("/remove", methods=["DELETE"])
def remove_item():
    data = request.get_json(force=True)
    token = data.get("token") or request.headers.get("X-Cart-Token")
    item_id = data.get("item_id")

    if not token:
        return err("Cart token required")
    cart = Cart.query.filter_by(session_token=token).first()
    if not cart:
        return err("Cart not found", 404)

    item = CartItem.query.filter_by(id=item_id, cart_id=cart.id).first()
    if item:
        db.session.delete(item)
        db.session.commit()
    return ok({"cart": cart.to_dict()}, "Item removed")


# ─── APPLY COUPON
@cart_bp.route("/coupon", methods=["POST"])
def apply_coupon():
    data = request.get_json(force=True)
    token = data.get("token") or request.headers.get("X-Cart-Token")
    code = (data.get("code") or "").strip().upper()

    if not token:
        return err("Cart token required")
    cart = Cart.query.filter_by(session_token=token).first()
    if not cart:
        return err("Cart not found", 404)

    coupon = Coupon.query.filter_by(code=code).first()
    if not coupon:
        return err("Invalid coupon code")

    valid, msg = coupon.is_valid(float(cart.subtotal))
    if not valid:
        return err(msg)

    discount = coupon.calculate_discount(float(cart.subtotal))
    cart.coupon_id = coupon.id
    db.session.commit()

    return ok({
        "cart": cart.to_dict(),
        "discount": discount,
        "message": f"Coupon applied! You save {discount:,.0f} TZS",
    })


@cart_bp.route("/coupon", methods=["DELETE"])
def remove_coupon():
    data = request.get_json(force=True)
    token = data.get("token") or request.headers.get("X-Cart-Token")
    if not token:
        return err("Cart token required")
    cart = Cart.query.filter_by(session_token=token).first()
    if cart:
        cart.coupon_id = None
        db.session.commit()
    return ok(message="Coupon removed")



@cart_bp.route("/merge", methods=["POST"])
def merge_carts():
    """
    Merge source_token cart into target_token cart.
    Used when a user gets a new device/browser session.
    """
    data = request.get_json(force=True)
    source_token = data.get("source_token")
    target_token = data.get("target_token")

    if not source_token or not target_token:
        return err("source_token and target_token required")

    source_cart = Cart.query.filter_by(session_token=source_token).first()
    target_cart = _get_or_create_cart(target_token)

    if source_cart:
        for item in source_cart.items:
            existing = CartItem.query.filter_by(
                cart_id=target_cart.id,
                product_id=item.product_id,
                variant_id=item.variant_id,
            ).first()
            if existing:
                existing.quantity += item.quantity
            else:
                new_item = CartItem(
                    cart_id=target_cart.id,
                    product_id=item.product_id,
                    variant_id=item.variant_id,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                )
                db.session.add(new_item)
        db.session.delete(source_cart)

    db.session.commit()
    return ok({"cart": target_cart.to_dict(), "token": target_token}, "Carts merged")