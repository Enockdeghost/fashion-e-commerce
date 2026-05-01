def test_add_to_cart(client, session_token, sample_product):
    variant = sample_product.variants[0]
    resp = client.post("/api/cart/add", json={
        "token": session_token,
        "product_id": sample_product.id,
        "variant_id": variant.id,
        "quantity": 1,
    })
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert len(data["cart"]["items"]) == 1

def test_get_cart(client, cart_with_item):
    resp = client.get("/api/cart", headers={"X-Cart-Token": cart_with_item})
    assert resp.status_code == 200
    cart = resp.get_json()["data"]["cart"]
    assert len(cart["items"]) == 1

def test_update_cart_quantity(client, cart_with_item):
    # First get the cart to obtain item_id
    resp = client.get("/api/cart", headers={"X-Cart-Token": cart_with_item})
    item_id = resp.get_json()["data"]["cart"]["items"][0]["id"]
    # Update quantity
    resp = client.put("/api/cart/update", json={
        "token": cart_with_item,
        "item_id": item_id,
        "quantity": 3,
    })
    assert resp.status_code == 200
    updated = client.get("/api/cart", headers={"X-Cart-Token": cart_with_item})
    qty = updated.get_json()["data"]["cart"]["items"][0]["quantity"]
    assert qty == 3

def test_remove_cart_item(client, cart_with_item):
    resp = client.get("/api/cart", headers={"X-Cart-Token": cart_with_item})
    item_id = resp.get_json()["data"]["cart"]["items"][0]["id"]
    resp = client.delete("/api/cart/remove", json={
        "token": cart_with_item,
        "item_id": item_id,
    })
    assert resp.status_code == 200
    resp2 = client.get("/api/cart", headers={"X-Cart-Token": cart_with_item})
    assert len(resp2.get_json()["data"]["cart"]["items"]) == 0

def test_apply_coupon(client, cart_with_item, sample_coupon):
    client.post("/api/cart/coupon", json={
        "token": cart_with_item,
        "code": "LUXE10",
    })
    resp = client.get("/api/cart", headers={"X-Cart-Token": cart_with_item})
    coupon = resp.get_json()["data"]["cart"]["coupon"]
    assert coupon is not None
    assert coupon["code"] == "LUXE10"