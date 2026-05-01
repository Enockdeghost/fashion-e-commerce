
from datetime import datetime, timezone
from flask import Blueprint, request, g
from app.extensions import db
from app.models import Order, Payment
from app.utils.security import ok, err, is_valid_tz_phone, normalise_phone, sanitise_text

payments_bp = Blueprint("payments", __name__)


# ─── INITIATE CHECKOUT 

@payments_bp.route("/checkout", methods=["POST"])
def checkout():
    data = request.get_json(force=True)
    order_ref = data.get("order_id") or data.get("order_number")
    phone = sanitise_text(data.get("phone_number", ""))

    if not order_ref:
        return err("order_id or order_number is required")
    if not phone:
        return err("phone_number is required (Tigo Money)")
    if not is_valid_tz_phone(phone):
        return err("Invalid Tanzanian phone number. Expected format: 07XXXXXXXX or +25577XXXXXXXX")

    order = Order.query.filter(
        (Order.id == order_ref) | (Order.order_number == order_ref)
    ).first_or_404()

    if order.status not in ("pending",):
        return err(f"Order cannot be paid in '{order.status}' status")

    # Check if payment already pending
    existing = Payment.query.filter_by(order_id=order.id, status="pending").first()
    if existing:
        return ok({
            "message": "Payment already initiated. Check your phone.",
            "transaction_id": existing.transaction_id,
        })

    phone = normalise_phone(phone)

    # Create payment record
    payment = Payment(
        order_id=order.id,
        payment_method="tigo_money",
        phone_number=phone,
        amount=order.total,
        currency=order.currency,
        status="pending",
    )
    db.session.add(payment)
    db.session.flush()

    # Call Tigo API
    from app.services.payment_service import TigoMoneyService
    tigo = TigoMoneyService()
    result = tigo.initiate_payment(
        phone_number=phone,
        amount=float(order.total),
        order_id=order.order_number,
        currency=order.currency,
    )

    if result["success"]:
        payment.transaction_id = result["transaction_id"]
        payment.gateway_reference = result.get("token", "")
        db.session.commit()
        return ok({
            "message": result["message"],
            "transaction_id": result["transaction_id"],
            "order_number": order.order_number,
        }, "Payment initiated")
    else:
        payment.status = "failed"
        payment.gateway_response = result
        db.session.commit()
        return err(f"Payment initiation failed: {result['message']}", 502)


# ─── QUERY PAYMENT STATUS 

@payments_bp.route("/checkout/<order_ref>", methods=["GET"])
def payment_status(order_ref):
    order = Order.query.filter(
        (Order.id == order_ref) | (Order.order_number == order_ref)
    ).first_or_404()

    payment = (
        Payment.query
        .filter_by(order_id=order.id)
        .order_by(Payment.created_at.desc())
        .first()
    )
    if not payment:
        return err("No payment found for this order", 404)

    # Poll Tigo if still pending
    if payment.status == "pending":
        from app.services.payment_service import TigoMoneyService
        tigo = TigoMoneyService()
        result = tigo.query_payment_status(payment.transaction_id)
        remote_status = result.get("status", "pending")

        if remote_status in ("successful", "success"):
            _confirm_payment(order, payment)
        elif remote_status in ("failed", "cancelled"):
            payment.status = remote_status
            db.session.commit()

    return ok({
        "order_number": order.order_number,
        "order_status": order.status,
        "payment": payment.to_dict(),
    })


# ─── WEBHOOK (Tigo callback) 
@payments_bp.route("/payment/webhook", methods=["POST"])
def payment_webhook():
    # Signature verification
    raw_body = request.get_data()
    signature = request.headers.get("X-Tigo-Signature", "")

    from flask import current_app
    from app.services.payment_service import TigoMoneyService
    tigo = TigoMoneyService()

    if not tigo.verify_webhook_signature(raw_body, signature):
        return err("Invalid webhook signature", 403)

    data = request.get_json(force=True)
    parsed = tigo.parse_webhook(data)

    order = Order.query.filter(
        (Order.id == parsed["order_id"]) |
        (Order.order_number == parsed["order_id"])
    ).first()

    if not order:
        return {"status": "ok"}, 200  # Acknowledge but ignore unknown orders

    payment = Payment.query.filter_by(
        order_id=order.id, transaction_id=parsed["transaction_id"]
    ).first()

    if not payment:
        # Create from webhook
        payment = Payment(
            order_id=order.id,
            payment_method="tigo_money",
            transaction_id=parsed["transaction_id"],
            phone_number=parsed["phone_number"],
            amount=parsed["amount"],
            currency=order.currency,
            status="pending",
        )
        db.session.add(payment)
        db.session.flush()

    if parsed["status"] in ("successful", "success") and payment.status != "successful":
        _confirm_payment(order, payment)
    elif parsed["status"] in ("failed", "cancelled"):
        payment.status = parsed["status"]
        payment.gateway_response = data
        db.session.commit()

    return {"status": "ok"}, 200


def _confirm_payment(order: Order, payment: Payment):
    """Mark payment and order as paid."""
    from app.models import OrderStatusHistory
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    payment.status = "successful"
    payment.paid_at = now
    order.status = "paid"
    order.paid_at = now

    db.session.add(OrderStatusHistory(
        order_id=order.id,
        from_status="pending",
        to_status="paid",
        notes=f"Tigo Money payment confirmed. TxID: {payment.transaction_id}",
    ))
    db.session.commit()

    # Notifications
    try:
        from app.services.email_service import send_payment_receipt
        send_payment_receipt(order, payment)
    except Exception:
        pass