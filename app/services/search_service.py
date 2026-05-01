import elasticsearch

from flask import current_app
from app.models import Product
from app.extensions import db


def search_products(query: str, page: int = 1, per_page: int = 20) -> dict:
    """
    Search for active, non‑deleted products.
    Returns {'items': [...], 'total': int}.
    """
    # 1) Try Elasticsearch
    try:
        result = _elasticsearch_search(query, page, per_page)
        if result is not None:
            return result
    except Exception:
        pass

    # 2) SQL fallback
    return _sql_search(query, page, per_page)


def _elasticsearch_search(query: str, page: int, per_page: int) -> dict | None:
    """Return None if impossible (any error)."""
    es_url = current_app.config.get("ELASTICSEARCH_URL")
    if not es_url:
        return None

    client = elasticsearch.Elasticsearch([es_url])
    body = {
        "query": {
            "multi_match": {
                "query": query,
                "fields": ["name^3", "description", "tags", "brand", "category"],
                "fuzziness": "AUTO",
            }
        },
        "from": (page - 1) * per_page,
        "size": per_page,
        "_source": [
            "id", "name", "slug", "base_price",
            "primary_image", "category", "brand",
        ],
    }
    resp = client.search(index="products", body=body)
    hits = resp["hits"]["hits"]
    items = [
        {
            "id": h["_id"],
            **h["_source"],
            "_score": h["_score"],
        }
        for h in hits
    ]
    total = resp["hits"]["total"]["value"]
    return {"items": items, "total": total}


def _sql_search(query: str, page: int, per_page: int) -> dict:
    """SQL ILIKE search, ordered by sales popularity."""
    like = f"%{query}%"
    q = (
        Product.query
        .filter_by(is_active=True, is_deleted=False)
        .filter(
            db.or_(
                Product.name.ilike(like),
                Product.description.ilike(like),
                Product.sku.ilike(like),
            )
        )
        .order_by(Product.total_sold.desc())
    )
    paginated = q.paginate(page=page, per_page=per_page, error_out=False)
    items = [p.to_dict() for p in paginated.items]
    return {"items": items, "total": paginated.total}