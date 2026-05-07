from flask import Blueprint, request
from datetime import datetime, timezone, timedelta
from app.extensions import db
from app.models import Order, OrderItem, Product, AbandonedCart, Payment
from app.utils.security import admin_required, ok, err
from sqlalchemy import func

analytics_bp = Blueprint("analytics", __name__, url_prefix="/analytics")


@analytics_bp.route("/dashboard", methods=["GET"])
@admin_required
def dashboard():
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)

    # Total orders & revenue (all time)
    total_orders = Order.query.count()
    total_revenue = db.session.query(func.sum(Order.total)).filter(
        Order.status.in_(["paid", "processing", "shipped", "delivered"])
    ).scalar() or 0.0

    # Last 30 days
    recent_orders = Order.query.filter(Order.created_at >= thirty_days_ago).count()
    recent_revenue = db.session.query(func.sum(Order.total)).filter(
        Order.created_at >= thirty_days_ago,
        Order.status.in_(["paid", "processing", "shipped", "delivered"])
    ).scalar() or 0.0

    # Top 5 best‑selling products (by quantity sold)
    top_products_q = (
        db.session.query(
            Product.name,
            Product.sku,
            func.sum(OrderItem.quantity).label("total_qty")
        )
        .join(OrderItem, OrderItem.product_id == Product.id)
        .join(Order, Order.id == OrderItem.order_id)
        .filter(Order.status.in_(["paid", "processing", "shipped", "delivered"]))
        .group_by(Product.id)
        .order_by(func.sum(OrderItem.quantity).desc())
        .limit(5)
        .all()
    )
    top_products = [{"name": name, "sku": sku, "total_sold": int(total)} for name, sku, total in top_products_q]

    # Payment method distribution (all Tigo for now, but generic)
    payment_stats = {
        "tigo_money": Payment.query.filter_by(payment_method="tigo_money", status="successful").count(),
    }

    return ok({
        "total_orders": total_orders,
        "total_revenue": float(total_revenue),
        "recent_orders": recent_orders,
        "recent_revenue": float(recent_revenue),
        "top_products": top_products,
        "payment_methods": payment_stats,
    })


@analytics_bp.route("/revenue", methods=["GET"])
@admin_required
def revenue():
    days = request.args.get("days", 30, type=int)
    start_date = datetime.now(timezone.utc) - timedelta(days=days)

    rows = (
        db.session.query(
            func.date(Order.created_at).label("date"),
            func.sum(Order.total).label("revenue"),
            func.count(Order.id).label("orders")
        )
        .filter(Order.created_at >= start_date)
        .filter(Order.status.in_(["paid", "processing", "shipped", "delivered"]))
        .group_by(func.date(Order.created_at))
        .order_by("date")
        .all()
    )

    data = [{"date": str(row.date), "revenue": float(row.revenue), "orders": row.orders} for row in rows]
    return ok(data)


@analytics_bp.route("/abandoned-carts", methods=["GET"])
@admin_required
def abandoned_carts():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    q = AbandonedCart.query.order_by(AbandonedCart.created_at.desc())
    paginated = q.paginate(page=page, per_page=per_page, error_out=False)
    items = [{
        "session_token": a.session_token,
        "subtotal": float(a.subtotal) if a.subtotal else 0,
        "email": a.email,
        "recovery_sent": a.recovery_sent,
        "recovered": a.recovered,
        "created_at": a.created_at.isoformat(),
    } for a in paginated.items]

    return ok({
        "abandoned_carts": items,
        "pagination": {"page": page, "per_page": per_page, "total": paginated.total}
    })