from unittest.mock import patch

@patch("app.services.payment_service.TigoMoneyService.initiate_payment")
def test_checkout_success(mock_tigo, client, cart_with_item, sample_product):
    # Mock Tigo response
    mock_tigo.return_value = {
        "success": True,
        "transaction_id": "TXN123",
        "message": "Payment initiated",
        "token": "tok_abc"
    }

    payload = {
        "cart_token": cart_with_item,
        "customer_email": "guest@test.com",
        "customer_name": "Jane Doe",
        "phone_number": "0712345678",
        "shipping_street": "123 Ocean Road",
        "shipping_city": "Dar es Salaam",
    }
    resp = client.post("/api/checkout", json=payload)
    assert resp.status_code == 201
    data = resp.get_json()["data"]
    assert data["order_number"].startswith("ORD-")
    assert data["transaction_id"] == "TXN123"

def test_checkout_missing_email(client, cart_with_item):
    resp = client.post("/api/checkout", json={
        "cart_token": cart_with_item,
        "customer_name": "Jane",
        "phone_number": "0712345678"
    })
    assert resp.status_code == 400