import uuid
import random
import string
from datetime import datetime, timezone

def _uuid():
    return str(uuid.uuid4())

def _now():
    return datetime.now(timezone.utc)

def _gen_sku(prefix="SKU"):
    chars = string.ascii_uppercase + string.digits
    return f"{prefix}-{''.join(random.choices(chars, k=8))}"

def _gen_order_number():
    return f"ORD-{datetime.now().strftime('%Y%m%d')}-{''.join(random.choices(string.digits, k=6))}"