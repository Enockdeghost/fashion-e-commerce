
from flask import Blueprint, request
from app.extensions import db
from app.models import Cart, Order, OrderItem, OrderStatusHistory, Payment
from app.utils.security import ok, err, sanitise_text, is_valid_tz_phone, normalise_phone, is_valid_email
from app.services.payment_service import TigoMoneyService
from datetime import datetime, timezone

checkout_bp = Blueprint("checkout", __name__, url_prefix="/checkout")


@checkout_bp.route("", methods=["POST"])
def process_checkout():
    data = request.get_json(silent=True) or {}

    # 1. Get and validate cart
    cart_token = data.get("cart_token")
    if not cart_token:
        return err("cart_token is required")
    cart = Cart.query.filter_by(session_token=cart_token).first()
    if not cart or cart.is_expired:
        return err("Cart is empty or expired")

    if cart.items.count() == 0:
        return err("Cart is empty")

    # 2. Validate required customer fields
    email = sanitise_text(data.get("customer_email", "")).lower().strip()
    name = sanitise_text(data.get("customer_name", ""))
    phone = sanitise_text(data.get("phone_number", ""))

    if not is_valid_email(email):
        return err("Valid customer_email is required")
    if not name:
        return err("customer_name is required")
    if not is_valid_tz_phone(phone):
        return err("Valid Tanzanian phone number is required")

    # 3. Check stock for each cart item
    for item in cart.items:
        if item.variant and item.variant.available_stock < item.quantity:
            return err(f"Insufficient stock for {item.product.name} ({item.variant.size}/{item.variant.color})")

    # 4. Calculate totals (subtotal, discount, shipping)
    subtotal = float(cart.subtotal)
    discount_amount = 0.0
    coupon_code = None
    if cart.coupon:
        valid, _ = cart.coupon.is_valid(subtotal)
        if valid:
            discount_amount = cart.coupon.calculate_discount(subtotal)
            coupon_code = cart.coupon.code
            cart.coupon.used_count += 1  # increment usage now

    # Simplified shipping (free over 500 TZS, else flat 25)
    shipping_amount = 0.0 if subtotal >= 500 else 25.0
    total = max(0, subtotal - discount_amount + shipping_amount)

    # 5. Create order (pending)
    order = Order(
        session_token=cart_token,
        customer_email=email,
        customer_name=name,
        customer_phone=normalise_phone(phone),
        shipping_name=sanitise_text(data.get("shipping_name", name)),
        shipping_phone=sanitise_text(data.get("shipping_phone", phone)),
        shipping_street=sanitise_text(data.get("shipping_street", "")),
        shipping_city=sanitise_text(data.get("shipping_city", "")),
        shipping_region=sanitise_text(data.get("shipping_region", "")),
        shipping_country=sanitise_text(data.get("shipping_country", "TZ")),
        shipping_postal_code=sanitise_text(data.get("shipping_postal_code", "")),
        currency=data.get("currency", "TZS"),
        subtotal=subtotal,
        discount_amount=discount_amount,
        shipping_amount=shipping_amount,
        tax_amount=0,
        total=total,
        coupon_id=cart.coupon_id,
        coupon_code=coupon_code,
        customer_notes=sanitise_text(data.get("customer_notes", "")),
        status="pending",
    )
    db.session.add(order)
    db.session.flush()  # get order.id

    for item in cart.items:
        oi = OrderItem(
            order_id=order.id,
            product_id=item.product_id,
            variant_id=item.variant_id,
            product_name=item.product.name,
            variant_sku=item.variant.sku if item.variant else None,
            size=item.variant.size if item.variant else None,
            color=item.variant.color if item.variant else None,
            quantity=item.quantity,
            unit_price=item.unit_price,
            line_total=item.line_total,
            image_url=item.product.primary_image,
        )
        db.session.add(oi)
        if item.variant:
            item.variant.reserved_stock += item.quantity

    # Status history
    db.session.add(OrderStatusHistory(
        order_id=order.id, from_status=None, to_status="pending",
        notes="Checkout by customer",
    ))

    # 7. Initiate Tigo payment
    payment = Payment(
        order_id=order.id,
        payment_method="tigo_money",
        phone_number=normalise_phone(phone),
        amount=order.total,
        currency=order.currency,
        status="pending",
    )
    db.session.add(payment)
    db.session.flush()

    tigo = TigoMoneyService()
    result = tigo.initiate_payment(
        phone_number=normalise_phone(phone),
        amount=float(order.total),
        order_id=order.order_number,
        currency=order.currency,
    )

    if not result["success"]:
        payment.status = "failed"
        db.session.commit()
        return err(f"Payment initiation failed: {result['message']}", 502)

    # Record successful initiation
    payment.transaction_id = result["transaction_id"]
    payment.gateway_reference = result.get("token", "")

    db.session.delete(cart)
    db.session.commit()

    # 8. Send confirmation email (non‑blocking best effort)
    try:
        from app.tasks import send_order_confirmation
        send_order_confirmation.delay(order.id)
    except Exception:
        pass

    return ok({
        "order_number": order.order_number,
        "transaction_id": result["transaction_id"],
        "message": result["message"],
    }, "Checkout completed", 201)