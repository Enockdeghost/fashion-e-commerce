
import re
from functools import wraps
from flask import request, jsonify

SKU_PATTERN = re.compile(r"^[A-Z0-9]{2,}-[A-Z0-9]{4,12}$")

def is_valid_sku(sku: str) -> bool:
    """Check if a string matches a typical SKU format, e.g. 'SKU-AB12CD34'."""
    return bool(SKU_PATTERN.match(sku.strip() if sku else ""))


def validate_integer(value, min_val: int = None, max_val: int = None):
    """Convert value to int and check bounds. Raises ValueError."""
    try:
        val = int(value)
    except (TypeError, ValueError):
        raise ValueError("Must be an integer")
    if min_val is not None and val < min_val:
        raise ValueError(f"Minimum value is {min_val}")
    if max_val is not None and val > max_val:
        raise ValueError(f"Maximum value is {max_val}")
    return val


def validate_price(amount) -> float:
    """Convert to float >= 0."""
    try:
        val = float(amount)
    except (TypeError, ValueError):
        raise ValueError("Invalid price")
    if val < 0:
        raise ValueError("Price cannot be negative")
    return round(val, 2)


def validate_iso_date(date_str: str) -> str:
    """Check if a string is a valid ISO date; return it stripped."""
    from datetime import datetime
    if not date_str:
        raise ValueError("Date is required")
    try:
        datetime.fromisoformat(date_str.strip())
    except ValueError:
        raise ValueError("Invalid ISO date format (YYYY-MM-DD)")
    return date_str.strip()


def validate_enum(value: str, allowed: list) -> str:
    """Raise ValueError if value not in allowed list."""
    if value not in allowed:
        raise ValueError(f"Value must be one of: {', '.join(allowed)}")
    return value


def require_fields(*fields, source="json"):
    """Decorator that ensures required fields exist in request data."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            data = request.get_json(silent=True) if source == "json" else request.form
            missing = [f for f in fields if f not in (data or {})]
            if missing:
                return jsonify({"success": False, "error": f"Missing fields: {', '.join(missing)}"}), 400
            return fn(*args, **kwargs)
        return wrapper
    return decorator