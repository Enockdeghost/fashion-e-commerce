def test_list_products(client, sample_product):
    resp = client.get("/api/products")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert len(data["data"]["products"]) >= 1

def test_get_product_by_id(client, sample_product):
    resp = client.get(f"/api/products/{sample_product.id}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["data"]["name"] == "Evening Gown"

def test_get_product_by_slug(client, sample_product):
    resp = client.get(f"/api/products/{sample_product.slug}")
    assert resp.status_code == 200
    assert resp.get_json()["data"]["id"] == sample_product.id

def test_create_product_admin(client, admin_token, sample_category, sample_brand):
    resp = client.post("/api/products", json={
        "name": "Silk Scarf",
        "base_price": 75000,
        "category_id": sample_category.id,
        "brand_id": sample_brand.id,
    }, headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["data"]["name"] == "Silk Scarf"

def test_update_product_admin(client, admin_token, sample_product):
    resp = client.put(f"/api/products/{sample_product.id}", json={
        "name": "Updated Gown",
        "base_price": 300000,
    }, headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert resp.get_json()["data"]["name"] == "Updated Gown"

def test_soft_delete_product_admin(client, admin_token, sample_product):
    resp = client.delete(f"/api/products/{sample_product.id}",
                         headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    # Verify soft delete
    product = Product.query.get(sample_product.id)
    assert product.is_deleted is True