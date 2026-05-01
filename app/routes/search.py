from app.services.search_service import search_products

@search_bp.route("", methods=["GET"])
def search():
    query = (request.args.get("q") or "").strip()
    if not query or len(query) < 2:
        return ok({"items": [], "total": 0})

    page, per_page = validate_pagination(request.args)
    result = search_products(query, page, per_page)

    return ok({
        "items": result["items"],
        "total": result["total"],
        "page": page,
        "per_page": per_page,
    })