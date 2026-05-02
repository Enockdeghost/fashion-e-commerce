from flask import Blueprint, request
from app.extensions import db
from app.models import Product
from app.utils.security import ok, err, validate_pagination

search_bp = Blueprint("search", __name__, url_prefix="/search")


def _es_search(query: str, page: int, per_page: int) -> dict:
    try:
        from flask import current_app
        from elasticsearch import Elasticsearch

        es = Elasticsearch([current_app.config["ELASTICSEARCH_URL"]])
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
            "_source": ["id", "name", "slug", "base_price", "primary_image", "category", "brand"],
        }
        
        resp = es.search(index="products", body=body)
        hits = resp["hits"]["hits"]
        items = [
            {
                "id": h["_source"].get("id"),
                "name": h["_source"].get("name"),
                "slug": h["_source"].get("slug"),
                "base_price": h["_source"].get("base_price"),
                "primary_image": h["_source"].get("primary_image"),
                "category": h["_source"].get("category"),
                "brand": h["_source"].get("brand"),
                "_score": h["_score"],
            }
            for h in hits
        ]
        total = resp["hits"]["total"]["value"]
        return {"items": items, "total": total}
    except Exception:
        return None


def _sql_search(query: str, page: int, per_page: int) -> dict:
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


@search_bp.route("", methods=["GET"])
def search():
    query = (request.args.get("q") or "").strip()
    if not query or len(query) < 2:
        return ok({"items": [], "total": 0})

    page, per_page = validate_pagination(request.args)

    result = _es_search(query, page, per_page)
    if result is None:
        result = _sql_search(query, page, per_page)

    return ok({
        "items": result["items"],
        "total": result["total"],
        "page": page,
        "per_page": per_page,
    })