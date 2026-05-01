
from flask import Blueprint, request
from app.utils.security import admin_required, ok, err
from app.models import Order, Payment

notifications_bp = Blueprint("notifications", __name__, url_prefix="/notifications")


@notifications_bp.route("/order-confirmation", methods=["POST"])
@admin_required
def resend_order_confirmation():
    data = request.get_json(silent=True) or {}
    order_ref = data.get("order_id") or data.get("order_number")
    if not order_ref:
        return err("order_id or order_number is required")

    order = Order.query.filter(
        (Order.id == order_ref) | (Order.order_number == order_ref)
    ).first()

    if not order:
        return err("Order not found", 404)

    try:
        from app.services.email_service import send_order_confirmation
        success = send_order_confirmation(order)
        if success:
            return ok(message=f"Confirmation email sent to {order.customer_email}")
        else:
            return err("Failed to send email", 502)
    except Exception as e:
        return err(f"Error: {str(e)}", 500)


@notifications_bp.route("/shipping-update", methods=["POST"])
@admin_required
def resend_shipping_notification():
    data = request.get_json(silent=True) or {}
    order_ref = data.get("order_id") or data.get("order_number")
    if not order_ref:
        return err("order_id or order_number is required")

    order = Order.query.filter(
        (Order.id == order_ref) | (Order.order_number == order_ref)
    ).first()

    if not order:
        return err("Order not found", 404)
    if order.status not in ("shipped",):
        return err("Order is not in 'shipped' status")

    try:
        from app.services.email_service import send_shipping_notification
        success = send_shipping_notification(order)
        return ok(message=f"Shipping notification sent to {order.customer_email}") if success else err("Failed", 502)
    except Exception as e:
        return err(str(e), 500)


@notifications_bp.route("/payment-receipt", methods=["POST"])
@admin_required
def resend_payment_receipt():
    data = request.get_json(silent=True) or {}
    order_ref = data.get("order_id") or data.get("order_number")
    if not order_ref:
        return err("order_id or order_number is required")

    order = Order.query.filter(
        (Order.id == order_ref) | (Order.order_number == order_ref)
    ).first()

    if not order:
        return err("Order not found", 404)

    payment = Payment.query.filter_by(order_id=order.id, status="successful").first()
    if not payment:
        return err("No successful payment found for this order")

    try:
        from app.services.email_service import send_payment_receipt
        success = send_payment_receipt(order, payment)
        return ok(message=f"Payment receipt sent to {order.customer_email}") if success else err("Failed", 502)
    except Exception as e:
        return err(str(e), 500)