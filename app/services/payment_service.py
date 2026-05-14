# this is imagination API client for Tigo Money, a popular mobile money service in Tanzania. so unaweza KUWEKA api yako
# It provides methods to initiate payments, query status, and verify webhooks. but not actual code, just a placeholder to show where payment logic would go.
import hmac
import hashlib
import requests
import logging
from flask import current_app
from datetime import datetime   

log = logging.getLogger(__name__)


class TigoMoneyService:
    """
    Wraps Tigo Money USSD Push & REST API calls.
    Docs: https://developer.tigo.com/docs/tigo-money
    """

    def __init__(self):
        self.base_url = current_app.config["TIGO_API_URL"]
        self.client_id = current_app.config["TIGO_CLIENT_ID"]
        self.client_secret = current_app.config["TIGO_CLIENT_SECRET"]
        self.merchant_id = current_app.config["TIGO_MERCHANT_ID"]
        self.pin = current_app.config["TIGO_PIN"]
        self._token = None

    # ── Auth 

    def _get_token(self) -> str | None:
        if self._token:
            return self._token
        try:
            resp = requests.post(
                f"{self.base_url}/oauth/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                timeout=15,
            )
            resp.raise_for_status()
            self._token = resp.json().get("access_token")
            return self._token
        except Exception as e:
            log.error(f"Tigo auth error: {e}")
            return None

    def _headers(self) -> dict:
        token = self._get_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    # ── Initiate USSD Pus
    def initiate_payment(
        self,
        phone_number: str,
        amount: float,
        order_id: str,
        currency: str = "TZS",
    ) -> dict:
        """
        Push a payment request to the customer's Tigo Money wallet.
        Returns: {"success": bool, "transaction_id": str, "message": str}
        """
        payload = {
            "MasterMerchant": {
                "account": self.merchant_id,
                "id": self.client_id,
                "pin": self.pin,
            },
            "Merchant": {
                "reference": order_id[:20],
                "fee": "0",
                "currencyCode": currency,
            },
            "Subscriber": {
                "account": phone_number,
                "countryCode": "255",
                "country": "TZA",
            },
            "redirectUri": "",
            "language": "EN",
            "terminalId": "web",
            "originPayment": {
                "amount": str(amount),
                "currencyCode": currency,
                "tax": "0",
                "fee": "0",
            },
        }

        try:
            resp = requests.post(
                f"{self.base_url}/payment/token/create",
                json=payload,
                headers=self._headers(),
                timeout=30,
            )
            data = resp.json()

            if resp.status_code == 200 and data.get("status") == "Success":
                return {
                    "success": True,
                    "transaction_id": data.get("transactionRefId", ""),
                    "token": data.get("payToken", ""),
                    "message": "Payment request sent to your Tigo Money wallet",
                }
            else:
                return {
                    "success": False,
                    "transaction_id": "",
                    "message": data.get("description", "Payment initiation failed"),
                }

        except Exception as e:
            log.error(f"Tigo initiate error: {e}")
            return {"success": False, "transaction_id": "", "message": str(e)}

    # ── Query Status 

    def query_payment_status(self, transaction_id: str) -> dict:
        """Check current status of a Tigo transaction."""
        try:
            resp = requests.get(
                f"{self.base_url}/payment/status/{transaction_id}",
                headers=self._headers(),
                timeout=15,
            )
            data = resp.json()
            return {
                "status": data.get("paymentStatus", "unknown").lower(),
                "raw": data,
            }
        except Exception as e:
            log.error(f"Tigo status query error: {e}")
            return {"status": "error", "raw": {}}

    # ── Webhook Verification 

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify Tigo's HMAC-SHA256 webhook signature."""
        expected = hmac.new(
            self.client_secret.encode(), payload, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature or "")

    # ── Parse Webhook 
    def parse_webhook(self, data: dict) -> dict:
        """
        Normalise Tigo webhook payload.
        Returns: {"order_id", "status", "transaction_id", "amount"}
        """
        return {
            "order_id": data.get("merchantReference", ""),
            "transaction_id": data.get("transactionRefId", ""),
            "status": data.get("paymentStatus", "").lower(),
            "amount": float(data.get("amount", 0)),
            "phone_number": data.get("subscriberMsisdn", ""),
        }

    # ── Refund
    def refund(self, transaction_id: str, amount: float, reason: str = "") -> dict:
        payload = {
            "transactionRefId": transaction_id,
            "amount": str(amount),
            "reason": reason or "Customer refund",
        }
        try:
            resp = requests.post(
                f"{self.base_url}/payment/refund",
                json=payload,
                headers=self._headers(),
                timeout=30,
            )
            data = resp.json()
            success = data.get("status", "").lower() == "success"
            return {"success": success, "message": data.get("description", ""), "raw": data}
        except Exception as e:
            log.error(f"Tigo refund error: {e}")
            return {"success": False, "message": str(e)}