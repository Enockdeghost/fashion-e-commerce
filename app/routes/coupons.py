
from flask import Blueprint, request
from app.models import Coupon
from app.utils.security import ok, err, sanitise_text

coupons_bp = Blueprint("coupons", __name__, url_prefix="/coupons")


@coupons_bp.route("/validate", methods=["POST"])
def validate_coupon():
    data = request.get_json(silent=True) or {}
    code = sanitise_text(data.get("code", "")).upper().strip()
    if not code:
        return err("Coupon code is required")

    coupon = Coupon.query.filter_by(code=code).first()
    if not coupon:
        return err("Invalid coupon code")

    valid, reason = coupon.is_valid(0)   # we don't know the order subtotal yet
    if not valid:
        return err(reason)

    # Return discount details without a subtotal – frontend will handle actual calculation
    return ok({
        "code": coupon.code,
        "discount_type": coupon.discount_type,
        "discount_value": float(coupon.discount_value),
        "minimum_purchase": float(coupon.minimum_purchase),
        "maximum_discount": float(coupon.maximum_discount) if coupon.maximum_discount else None,
        "description": coupon.description,
    }, "Coupon is valid")