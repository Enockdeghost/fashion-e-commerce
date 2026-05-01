
from flask import Blueprint, request, g
from app.extensions import db
from app.models import ProductVariant, InventoryLog, Product
from app.utils.security import admin_required, validate_pagination, ok, err

inventory_bp = Blueprint("inventory", __name__, url_prefix="/inventory")


@inventory_bp.route("", methods=["GET"])
@admin_required
def list_inventory():
    page, per_page = validate_pagination(request.args)
    q = ProductVariant.query.join(Product).filter(
        Product.is_deleted == False, ProductVariant.is_active == True
    )
    if search := request.args.get("q"):
        like = f"%{search}%"
        q = q.filter(ProductVariant.sku.ilike(like) | Product.name.ilike(like))

    paginated = q.paginate(page=page, per_page=per_page, error_out=False)

    return ok({
        "variants": [
            {
                **v.to_dict(),
                "product_name": v.product.name,
                "product_id": v.product_id,
            }
            for v in paginated.items
        ],
        "pagination": {
            "page": page, "per_page": per_page, "total": paginated.total,
        },
    })


@inventory_bp.route("/low-stock", methods=["GET"])
@admin_required
def low_stock():
    from flask import current_app
    threshold = int(request.args.get("threshold", current_app.config["LOW_STOCK_THRESHOLD"]))
    variants = (
        ProductVariant.query
        .join(Product)
        .filter(
            Product.is_deleted == False,
            ProductVariant.is_active == True,
            ProductVariant.stock > 0,
            ProductVariant.stock <= threshold,
        )
        .all()
    )
    return ok([
        {**v.to_dict(), "product_name": v.product.name}
        for v in variants
    ])


@inventory_bp.route("/out-of-stock", methods=["GET"])
@admin_required
def out_of_stock():
    variants = (
        ProductVariant.query
        .join(Product)
        .filter(Product.is_deleted == False, ProductVariant.stock <= 0)
        .all()
    )
    return ok([
        {**v.to_dict(), "product_name": v.product.name}
        for v in variants
    ])


@inventory_bp.route("/<variant_id>", methods=["PUT"])
@admin_required
def adjust_stock(variant_id):
    variant = ProductVariant.query.get_or_404(variant_id)
    data = request.get_json(force=True)

    change_type = data.get("change_type", "adjustment")
    quantity_change = int(data.get("quantity_change", 0))
    notes = data.get("notes", "")

    if change_type not in ("restock", "adjustment", "return", "write_off"):
        return err("Invalid change_type")

    qty_before = variant.stock
    variant.stock = max(0, variant.stock + quantity_change)
    qty_after = variant.stock

    log = InventoryLog(
        variant_id=variant_id,
        change_type=change_type,
        quantity_before=qty_before,
        quantity_change=quantity_change,
        quantity_after=qty_after,
        notes=notes,
        admin_id=g.admin.id,
    )
    db.session.add(log)
    db.session.commit()

    # Send low stock alert if needed
    from flask import current_app
    if variant.is_low_stock:
        try:
            from app.services.email_service import send_admin_low_stock_alert
            send_admin_low_stock_alert(variant, current_app.config["SUPER_ADMIN_EMAIL"])
        except Exception:
            pass

    return ok({
        "variant": variant.to_dict(),
        "log": log.to_dict(),
    }, "Stock updated")


@inventory_bp.route("/<variant_id>/logs", methods=["GET"])
@admin_required
def variant_logs(variant_id):
    page, per_page = validate_pagination(request.args)
    variant = ProductVariant.query.get_or_404(variant_id)
    logs = (
        InventoryLog.query
        .filter_by(variant_id=variant_id)
        .order_by(InventoryLog.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )
    return ok({
        "variant": variant.to_dict(),
        "logs": [l.to_dict() for l in logs.items],
        "pagination": {"page": page, "total": logs.total},
    })