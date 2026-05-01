def test_get_order_by_id(client, sample_product, cart_with_item):
    # First create an order via checkout (mock Tigo)
    with patch("app.services.payment_service.TigoMoneyService.initiate_payment") as mock:
        mock.return_value = {
            "success": True,
            "transaction_id": "TXN123",
            "message": "ok",
            "token": "tok"
        }
        ch = client.post("/api/checkout", json={
            "cart_token": cart_with_item,
            "customer_email": "a@b.com",
            "customer_name": "Test",
            "phone_number": "0712345678",
        })
        order_number = ch.get_json()["data"]["order_number"]

    # Fetch order by number
    resp = client.get(f"/api/orders/{order_number}?email=a@b.com")
    assert resp.status_code == 200
    order = resp.get_json()["data"]
    assert order["order_number"] == order_number
    assert len(order["items"]) > 0