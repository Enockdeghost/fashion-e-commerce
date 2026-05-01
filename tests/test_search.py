def test_search_with_results(client, sample_product):
    # Search for "gown"
    resp = client.get("/api/search?q=gown")
    assert resp.status_code == 200
    items = resp.get_json()["data"]["items"]
    assert any("gown" in item["name"].lower() for item in items)