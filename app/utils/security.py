
import re
import secrets
import bleach
from functools import wraps
from flask import request, jsonify, g
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from app.models import AdminUser


_ALLOWED_TAGS = [
    "p", "br", "strong", "em", "ul", "ol", "li", "h1", "h2", "h3",
    "blockquote", "a", "span", "img",
]
_ALLOWED_ATTRS = {
    "a": ["href", "title", "rel"],
    "img": ["src", "alt", "width", "height"],
    "span": ["class"],
}


def sanitise_html(raw: str) -> str:
    """Strip dangerous HTML while allowing a safe subset."""
    return bleach.clean(raw, tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRS, strip=True)


def sanitise_text(raw: str) -> str:
    """Remove all HTML tags and strip whitespace."""
    return bleach.clean(raw, tags=[], strip=True).strip()



def admin_required(fn):
    """Require a valid JWT and any admin role."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request()
            admin_id = get_jwt_identity()
            admin = AdminUser.query.get(admin_id)
            if not admin or not admin.is_active:
                return jsonify({"error": "Unauthorised"}), 401
            g.admin = admin
        except Exception:
            return jsonify({"error": "Invalid or expired token"}), 401
        return fn(*args, **kwargs)
    return wrapper


def roles_required(*roles):
    """Require a valid JWT AND that the admin's role is in *roles*."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                verify_jwt_in_request()
                admin_id = get_jwt_identity()
                admin = AdminUser.query.get(admin_id)
                if not admin or not admin.is_active:
                    return jsonify({"error": "Unauthorised"}), 401
                if admin.role not in roles:
                    return jsonify({"error": "Forbidden — insufficient permissions"}), 403
                g.admin = admin
            except Exception:
                return jsonify({"error": "Invalid or expired token"}), 401
            return fn(*args, **kwargs)
        return wrapper
    return decorator


# ─── Secure headers middleware 

def add_security_headers(response):
    """Called via app.after_request to attach security headers."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "img-src 'self' data: https://res.cloudinary.com; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline';"
    )
    return response



def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def validate_csrf_token(token: str, stored: str) -> bool:
    return secrets.compare_digest(token or "", stored or "")



EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_TZ_RE = re.compile(r"^\+?255[67]\d{8}$")   # Tanzanian mobile
MSISDN_RE = re.compile(r"^0[67]\d{8}$")           # local format


def is_valid_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email or ""))


def is_valid_tz_phone(phone: str) -> bool:
    phone = (phone or "").replace(" ", "").replace("-", "")
    return bool(PHONE_TZ_RE.match(phone) or MSISDN_RE.match(phone))


def normalise_phone(phone: str) -> str:
    """Convert 0712345678 → +255712345678."""
    phone = phone.strip().replace(" ", "").replace("-", "")
    if phone.startswith("0"):
        return "+255" + phone[1:]
    if phone.startswith("255") and not phone.startswith("+"):
        return "+" + phone
    return phone


def validate_pagination(args) -> tuple:
    try:
        page = max(1, int(args.get("page", 1)))
    except (ValueError, TypeError):
        page = 1
    try:
        per_page = min(100, max(1, int(args.get("per_page", 20))))
    except (ValueError, TypeError):
        per_page = 20
    return page, per_page


# ─── JSON response helpers 

def ok(data=None, message="Success", status=200):
    body = {"success": True, "message": message}
    if data is not None:
        body["data"] = data
    return jsonify(body), status


def err(message="Error", status=400, errors=None):
    body = {"success": False, "error": message}
    if errors:
        body["errors"] = errors
    return jsonify(body), status