def test_admin_login(client, admin_user):
    resp = client.post("/api/admin/login", json={
        "email": "admin@test.com",
        "password": "password123",
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert "access_token" in data["data"]

def test_admin_invalid_login(client):
    resp = client.post("/api/admin/login", json={
        "email": "wrong@test.com",
        "password": "wrong",
    })
    assert resp.status_code == 401

def test_admin_me(client, admin_token):
    resp = client.get("/api/admin/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert resp.get_json()["data"]["admin"]["email"] == "admin@test.com"