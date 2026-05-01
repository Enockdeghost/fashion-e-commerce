"""
Email notification service using SendGrid.
Handles: order confirmation, shipping, payment receipts, admin alerts.
"""
import sendgrid
from sendgrid.helpers.mail import Mail, To, From, Subject, HtmlContent
from flask import current_app
import logging

log = logging.getLogger(__name__)


def _client():
    return sendgrid.SendGridAPIClient(api_key=current_app.config["SENDGRID_API_KEY"])


def _send(to_email: str, subject: str, html_body: str) -> bool:
    try:
        message = Mail(
            from_email=(current_app.config["FROM_EMAIL"], current_app.config["FROM_NAME"]),
            to_emails=to_email,
            subject=subject,
            html_content=html_body,
        )
        response = _client().send(message)
        return response.status_code in (200, 202)
    except Exception as e:
        log.error(f"SendGrid error: {e}")
        return False


# ─── Order Emails 
def send_order_confirmation(order) -> bool:
    items_html = "".join(
        f"<tr><td>{i.product_name}</td><td>{i.quantity}</td>"
        f"<td>{i.unit_price:,.0f} {order.currency}</td></tr>"
        for i in order.items
    )
    html = f"""
    <div style="font-family:sans-serif;max-width:600px;margin:auto">
      <h1 style="color:#111">Order Confirmed</h1>
      <p>Hi {order.customer_name}, thank you for your order!</p>
      <p><strong>Order:</strong> {order.order_number}</p>
      <table width="100%" cellpadding="8" style="border-collapse:collapse">
        <tr style="background:#f5f5f5">
          <th>Item</th><th>Qty</th><th>Price</th>
        </tr>
        {items_html}
        <tr><td colspan="2"><strong>Total</strong></td>
            <td><strong>{order.total:,.0f} {order.currency}</strong></td></tr>
      </table>
      <p>We will notify you when your order ships.</p>
    </div>
    """
    return _send(order.customer_email, f"Order Confirmed – {order.order_number}", html)


def send_shipping_notification(order) -> bool:
    html = f"""
    <div style="font-family:sans-serif;max-width:600px;margin:auto">
      <h1 style="color:#111">Your Order Has Shipped!</h1>
      <p>Hi {order.customer_name},</p>
      <p>Your order <strong>{order.order_number}</strong> is on its way.</p>
      <p><strong>Courier:</strong> {order.courier}</p>
      <p><strong>Tracking Number:</strong> {order.tracking_number}</p>
      <p>Estimated delivery: {order.estimated_delivery.strftime('%d %b %Y') if order.estimated_delivery else 'TBD'}</p>
    </div>
    """
    return _send(order.customer_email, f"Your Order {order.order_number} Has Shipped", html)


def send_payment_receipt(order, payment) -> bool:
    html = f"""
    <div style="font-family:sans-serif;max-width:600px;margin:auto">
      <h1 style="color:#111">Payment Received</h1>
      <p>Hi {order.customer_name},</p>
      <p>We received your payment for order <strong>{order.order_number}</strong>.</p>
      <table width="100%" cellpadding="8">
        <tr><td>Payment Method</td><td>{payment.payment_method.replace('_',' ').title()}</td></tr>
        <tr><td>Transaction ID</td><td>{payment.transaction_id}</td></tr>
        <tr><td>Amount</td><td>{payment.amount:,.0f} {payment.currency}</td></tr>
      </table>
      <p>Your order is now being processed.</p>
    </div>
    """
    return _send(order.customer_email, f"Payment Receipt – {order.order_number}", html)


def send_order_cancelled(order) -> bool:
    html = f"""
    <div style="font-family:sans-serif;max-width:600px;margin:auto">
      <h1 style="color:#c00">Order Cancelled</h1>
      <p>Hi {order.customer_name},</p>
      <p>Your order <strong>{order.order_number}</strong> has been cancelled.</p>
      <p>If you paid, a refund will be processed within 3–5 business days.</p>
      <p>If you have questions, reply to this email.</p>
    </div>
    """
    return _send(order.customer_email, f"Order {order.order_number} Cancelled", html)


def send_refund_notification(order) -> bool:
    html = f"""
    <div style="font-family:sans-serif;max-width:600px;margin:auto">
      <h1 style="color:#111">Refund Processed</h1>
      <p>Hi {order.customer_name},</p>
      <p>Your refund for order <strong>{order.order_number}</strong> of 
         <strong>{order.total:,.0f} {order.currency}</strong> has been processed.</p>
      <p>Please allow 3–5 business days for the funds to reflect.</p>
    </div>
    """
    return _send(order.customer_email, f"Refund Processed – {order.order_number}", html)


# ─── Admin Alerts 

def send_admin_low_stock_alert(variant, admin_email: str) -> bool:
    html = f"""
    <div style="font-family:sans-serif;max-width:600px;margin:auto">
      <h2 style="color:#e65100">⚠ Low Stock Alert</h2>
      <p>SKU <strong>{variant.sku}</strong> has only 
         <strong>{variant.available_stock}</strong> units left.</p>
      <p>Product: {variant.product.name}</p>
      <p>Size: {variant.size} / Color: {variant.color}</p>
    </div>
    """
    return _send(admin_email, f"Low Stock Alert – SKU {variant.sku}", html)


def send_admin_new_order_alert(order, admin_email: str) -> bool:
    html = f"""
    <div style="font-family:sans-serif;max-width:600px;margin:auto">
      <h2>🛍 New Order Received</h2>
      <p>Order <strong>{order.order_number}</strong> from 
         <strong>{order.customer_name}</strong> ({order.customer_email})</p>
      <p>Total: <strong>{order.total:,.0f} {order.currency}</strong></p>
    </div>
    """
    return _send(admin_email, f"New Order – {order.order_number}", html)