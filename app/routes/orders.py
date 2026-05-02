import io
from datetime import datetime, timezone
from flask import Blueprint, request, send_file, g
from app.extensions import db
from app.models import (
    Order, OrderItem, OrderStatusHistory,
    Cart, CartItem, Product, ProductVariant, Coupon, Payment,
    ShippingZone, ShippingRate,
)
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.units import cm
from app.utils.security import admin_required, ok, err, sanitise_text, validate_pagination

orders_bp = Blueprint("orders", __name__, url_prefix="/orders")


@orders_bp.route("", methods=["POST"])
def create_order():
    data = request.get_json(force=True)

    cart_token = data.get("cart_token")
    if not cart_token:
        return err("cart_token is required")
    cart = Cart.query.filter_by(session_token=cart_token).first()
    if not cart or cart.is_expired:
        return err("Cart not found or expired")
    if not cart.items.count():
        return err("Cart is empty")

    email = sanitise_text(data.get("customer_email", ""))
    name = sanitise_text(data.get("customer_name", ""))
    from app.utils.security import is_valid_email
    if not is_valid_email(email):
        return err("Valid customer_email is required")
    if not name:
        return err("customer_name is required")

    for item in cart.items:
        if item.variant:
            if item.variant.available_stock < item.quantity:
                return err(
                    f"Insufficient stock for {item.product.name} "
                    f"({item.variant.size}/{item.variant.color})"
                )

    shipping_rate_id = data.get("shipping_rate_id")
    shipping_amount = 0.0
    shipping_zone_id = None
    courier = None
    shipping_rate = None
    if shipping_rate_id:
        shipping_rate = ShippingRate.query.get(shipping_rate_id)
        if shipping_rate:
            shipping_amount = float(shipping_rate.rate)
            shipping_zone_id = shipping_rate.zone_id
            courier = shipping_rate.name

    discount_amount = 0.0
    coupon_code = None
    coupon = cart.coupon
    subtotal = float(cart.subtotal)
    if coupon:
        valid, _ = coupon.is_valid(subtotal)
        if valid:
            discount_amount = coupon.calculate_discount(subtotal)
            coupon_code = coupon.code
            coupon.used_count += 1

    total = max(0, subtotal - discount_amount + shipping_amount)

    order = Order(
        session_token=cart_token,
        customer_email=email,
        customer_name=name,
        customer_phone=sanitise_text(data.get("customer_phone", "")),
        shipping_name=sanitise_text(data.get("shipping_name", name)),
        shipping_phone=sanitise_text(data.get("shipping_phone", "")),
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
        coupon_id=coupon.id if coupon else None,
        coupon_code=coupon_code,
        shipping_zone_id=shipping_zone_id,
        shipping_rate_id=shipping_rate_id,
        courier=courier,
        customer_notes=sanitise_text(data.get("customer_notes", "")),
        status="pending",
    )
    db.session.add(order)
    db.session.flush()

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

    db.session.add(OrderStatusHistory(
        order_id=order.id, from_status=None, to_status="pending",
        notes="Order placed by customer",
    ))

    db.session.delete(cart)
    db.session.commit()

    try:
        from app.services.email_service import send_order_confirmation
        send_order_confirmation(order)
    except Exception:
        pass

    try:
        from flask import current_app
        from app.services.email_service import send_admin_new_order_alert
        send_admin_new_order_alert(order, current_app.config["SUPER_ADMIN_EMAIL"])
    except Exception:
        pass

    return ok(order.to_dict(full=True), "Order created successfully", 201)


@orders_bp.route("/<order_ref>", methods=["GET"])
def get_order(order_ref):
    order = Order.query.filter(
        (Order.id == order_ref) | (Order.order_number == order_ref)
    ).first_or_404()

    provided_email = request.args.get("email", "").lower().strip()
    if provided_email and order.customer_email.lower() != provided_email:
        return err("Order not found", 404)

    return ok(order.to_dict(full=True))


@orders_bp.route("", methods=["GET"])
@admin_required
def list_orders():
    page, per_page = validate_pagination(request.args)
    q = Order.query

    if status := request.args.get("status"):
        q = q.filter(Order.status == status)
    if search := request.args.get("q"):
        like = f"%{search}%"
        q = q.filter(
            (Order.order_number.ilike(like)) |
            (Order.customer_email.ilike(like)) |
            (Order.customer_name.ilike(like))
        )
    if date_from := request.args.get("from"):
        q = q.filter(Order.created_at >= datetime.fromisoformat(date_from))
    if date_to := request.args.get("to"):
        q = q.filter(Order.created_at <= datetime.fromisoformat(date_to))

    q = q.order_by(Order.created_at.desc())
    paginated = q.paginate(page=page, per_page=per_page, error_out=False)

    return ok({
        "orders": [o.to_dict() for o in paginated.items],
        "pagination": {
            "page": page, "per_page": per_page,
            "total": paginated.total, "pages": paginated.pages,
        },
    })


@orders_bp.route("/<order_id>/status", methods=["PUT"])
@admin_required
def update_status(order_id):
    order = Order.query.get_or_404(order_id)
    data = request.get_json(force=True)
    new_status = data.get("status")

    if new_status not in Order.ORDER_STATUSES:
        return err(f"Invalid status. Allowed: {Order.ORDER_STATUSES}")

    old_status = order.status
    order.status = new_status

    now = datetime.now(timezone.utc)
    if new_status == "shipped":
        order.shipped_at = now
        order.tracking_number = data.get("tracking_number", order.tracking_number)
        order.courier = data.get("courier", order.courier)
    elif new_status == "delivered":
        order.delivered_at = now
        for item in order.items:
            if item.variant:
                v = item.variant
                v.reserved_stock = max(0, v.reserved_stock - item.quantity)
                v.stock = max(0, v.stock - item.quantity)
                v.product.total_sold += item.quantity
    elif new_status == "cancelled":
        order.cancelled_at = now
        for item in order.items:
            if item.variant:
                item.variant.reserved_stock = max(0, item.variant.reserved_stock - item.quantity)
    elif new_status == "paid":
        order.paid_at = now

    db.session.add(OrderStatusHistory(
        order_id=order.id,
        from_status=old_status,
        to_status=new_status,
        notes=sanitise_text(data.get("notes", "")),
        admin_id=g.admin.id,
    ))
    db.session.commit()

    try:
        from app.services import email_service as em
        if new_status == "shipped":
            em.send_shipping_notification(order)
        elif new_status == "cancelled":
            em.send_order_cancelled(order)
        elif new_status == "refunded":
            em.send_refund_notification(order)
    except Exception:
        pass

    return ok(order.to_dict(full=True), f"Order status updated to {new_status}")


@orders_bp.route("/<order_ref>/cancel", methods=["POST"])
def cancel_order(order_ref):
    data = request.get_json(force=True)
    order = Order.query.filter(
        (Order.id == order_ref) | (Order.order_number == order_ref)
    ).first_or_404()

    email = sanitise_text(data.get("email", ""))
    if order.customer_email.lower() != email.lower():
        return err("Email does not match order", 403)

    if order.status not in ("pending", "paid"):
        return err(f"Order cannot be cancelled in '{order.status}' status")

    order.status = "cancelled"
    order.cancelled_at = datetime.now(timezone.utc)
    for item in order.items:
        if item.variant:
            item.variant.reserved_stock = max(0, item.variant.reserved_stock - item.quantity)

    db.session.add(OrderStatusHistory(
        order_id=order.id, from_status="pending", to_status="cancelled",
        notes="Cancelled by customer",
    ))
    db.session.commit()

    try:
        from app.services.email_service import send_order_cancelled
        send_order_cancelled(order)
    except Exception:
        pass

    return ok(message="Order cancelled")


@orders_bp.route("/<order_ref>/return", methods=["POST"])
def request_return(order_ref):
    data = request.get_json(force=True)
    order = Order.query.filter(
        (Order.id == order_ref) | (Order.order_number == order_ref)
    ).first_or_404()

    email = sanitise_text(data.get("email", ""))
    if order.customer_email.lower() != email.lower():
        return err("Email does not match order", 403)

    if order.status != "delivered":
        return err("Only delivered orders can be returned")

    order.status = "return_requested"
    db.session.add(OrderStatusHistory(
        order_id=order.id,
        from_status="delivered",
        to_status="return_requested",
        notes=sanitise_text(data.get("reason", "Customer return request")),
    ))
    db.session.commit()
    return ok(message="Return request submitted")


@orders_bp.route("/<order_ref>/invoice", methods=["GET"])
def get_invoice(order_ref):
    order = Order.query.filter(
        (Order.id == order_ref) | (Order.order_number == order_ref)
    ).first_or_404()

    email = request.args.get("email", "")
    if email and order.customer_email.lower() != email.lower():
        return err("Unauthorised", 403)

    pdf_buffer = _generate_invoice_pdf(order)
    pdf_buffer.seek(0)
    return send_file(
        pdf_buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"invoice-{order.order_number}.pdf",
    )


def _generate_invoice_pdf(order) -> io.BytesIO:
    try:
        
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm,
                                topMargin=2*cm, bottomMargin=2*cm)
        styles = getSampleStyleSheet()
        story = []

        story.append(Paragraph("<b>LUXÉ FASHION</b>", ParagraphStyle(
            "brand", fontSize=24, textColor=colors.HexColor("#111111"), spaceAfter=4
        )))
        story.append(Paragraph("Premium Fashion House", ParagraphStyle(
            "sub", fontSize=10, textColor=colors.grey, spaceAfter=20
        )))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.black))
        story.append(Spacer(1, 0.5*cm))

        story.append(Paragraph(f"<b>INVOICE</b>", styles["h2"]))
        meta = [
            ["Order Number:", order.order_number],
            ["Date:", order.created_at.strftime("%d %B %Y")],
            ["Status:", order.status.upper()],
            ["Customer:", order.customer_name],
            ["Email:", order.customer_email],
        ]
        if order.shipping_city:
            meta.append(["Ship To:", f"{order.shipping_street}, {order.shipping_city}, {order.shipping_region}"])

        meta_table = Table(meta, colWidths=[4*cm, 12*cm])
        meta_table.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.grey),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 0.8*cm))

        headers = ["Item", "SKU", "Size", "Color", "Qty", "Unit Price", "Total"]
        rows = [headers]
        for item in order.items:
            rows.append([
                item.product_name or "—",
                item.variant_sku or "—",
                item.size or "—",
                item.color or "—",
                str(item.quantity),
                f"{float(item.unit_price):,.0f} {order.currency}",
                f"{float(item.line_total):,.0f} {order.currency}",
            ])

        item_table = Table(rows, colWidths=[4.5*cm, 2.5*cm, 1.5*cm, 2*cm, 1*cm, 2.5*cm, 2.5*cm])
        item_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.black),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9f9f9")]),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("ALIGN", (4, 0), (-1, -1), "RIGHT"),
        ]))
        story.append(item_table)
        story.append(Spacer(1, 0.5*cm))

        totals = [
            ["Subtotal:", f"{float(order.subtotal):,.0f} {order.currency}"],
            ["Discount:", f"- {float(order.discount_amount):,.0f} {order.currency}"],
            ["Shipping:", f"{float(order.shipping_amount):,.0f} {order.currency}"],
            ["", ""],
            ["TOTAL:", f"{float(order.total):,.0f} {order.currency}"],
        ]
        totals_table = Table(totals, colWidths=[13*cm, 3.5*cm])
        totals_table.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("FONTSIZE", (0, 4), (-1, 4), 12),
            ("FONTNAME", (0, 4), (-1, 4), "Helvetica-Bold"),
            ("LINEABOVE", (0, 4), (-1, 4), 1, colors.black),
        ]))
        story.append(totals_table)
        story.append(Spacer(1, 1*cm))
        story.append(Paragraph("Thank you for shopping with Luxé Fashion.", styles["Normal"]))

        doc.build(story)
        return buf

    except ImportError:
        buf = io.BytesIO()
        buf.write(b"%PDF-1.0 1 0 obj<</Type/Catalog>>endobj")
        return buf