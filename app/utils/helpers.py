
import secrets
import re
from datetime import datetime, timezone
from flask import request
from sqlalchemy.orm import Query


def generate_token(length: int = 32) -> str:
    """Cryptographically‑safe random token (URL‑safe)."""
    return secrets.token_urlsafe(length)


def format_currency(amount: float, currency: str = "TZS") -> str:
    """Format a number into a readable currency string, e.g. '125,000 TZS'."""
    try:
        amount = round(float(amount), 2)
    except (TypeError, ValueError):
        amount = 0.0
    if amount == int(amount):
        amount = int(amount)  # remove .00
    return f"{amount:,} {currency}"


def paginate_query(
    query: Query,
    page: int = 1,
    per_page: int = 20,
    max_per_page: int = 100
) -> tuple:
    """
    Paginate any SQLAlchemy query.
    Returns (items, pagination_meta) where meta is a dict.
    """
    page = max(1, int(page))
    per_page = min(max_per_page, max(1, int(per_page)))
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)
    meta = {
        "page": page,
        "per_page": per_page,
        "total": paginated.total,
        "pages": paginated.pages,
        "has_next": paginated.has_next,
        "has_prev": paginated.has_prev,
    }
    return paginated.items, meta


def apply_sorting(query: Query, sort_map: dict, default_sort=None):
    """
    Apply ordering to a query based on request arg 'sort'.
    sort_map: { 'key': Column.asc() / Column.desc() }
    """
    sort_key = request.args.get("sort", "")
    if sort_key in sort_map:
        return query.order_by(sort_map[sort_key])
    if default_sort is not None:
        return query.order_by(default_sort)
    return query


def parse_iso_date(date_str: str) -> datetime | None:
    """Parse ISO 8601 date string to UTC datetime, or return None."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def slugify_unique(base: str, model, field: str = "slug", separator: str = "-") -> str:
    """
    Generate a unique slug by appending a counter if needed.
    model is the SQLAlchemy model class, field the column to check.
    """
    from slugify import slugify
    slug = slugify(base, separator=separator)
    if not slug:
        slug = "item"
    original = slug
    counter = 1
    while getattr(model.query.filter(getattr(model, field) == slug), 'first')():
        slug = f"{original}{separator}{counter}"
        counter += 1
    return slug