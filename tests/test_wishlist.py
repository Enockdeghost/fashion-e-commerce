def test_add_to_wishlist(client, session_token, sample_product):
    resp = client.post("/api/wishlist", json={
        "token": session_token,
        "product_id": sample_product.id,
    })
    assert resp.status_code == 201

def test_get_wishlist(client, session_token, sample_product):
    client.post("/api/wishlist", json={"token": session_token, "product_id": sample_product.id})
    resp = client.get("/api/wishlist", headers={"X-Cart-Token": session_token})
    assert resp.status_code == 200
    assert len(resp.get_json()["data"]["wishlist"]) == 1

def test_remove_from_wishlist(client, session_token, sample_product):
    client.post("/api/wishlist", json={"token": session_token, "product_id": sample_product.id})
    resp = client.get("/api/wishlist", headers={"X-Cart-Token": session_token})
    item_id = resp.get_json()["data"]["wishlist"][0]["id"]
    resp = client.delete(f"/api/wishlist/{item_id}", headers={"X-Cart-Token": session_token})
    assert resp.status_code == 200