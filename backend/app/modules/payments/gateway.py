"""
Razorpay, the payment gateway (UPI, cards, net banking). Only these calls are used:
create an order, list an order's payments, and the two signature checks. Test-mode keys
(rzp_test_...) work end to end without real money.
"""

import hashlib
import hmac
from typing import Any

import httpx

from app.core.config import settings
from app.core.errors import AppError

API = "https://api.razorpay.com/v1"


def enabled() -> bool:
    return bool(settings.razorpay_key_id and settings.razorpay_key_secret)


def _auth() -> tuple[str, str]:
    if not enabled():
        raise AppError(503, "Online payment isn't set up yet. Please pay at the college counter.", "payments_off")
    assert settings.razorpay_key_id and settings.razorpay_key_secret
    return settings.razorpay_key_id, settings.razorpay_key_secret


def _call(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    try:
        res = httpx.request(method, f"{API}{path}", auth=_auth(), timeout=10, **kwargs)
        res.raise_for_status()
    except httpx.HTTPError as e:
        raise AppError(502, "The payment service didn't answer. Please try again in a minute.", "gateway_error") from e
    data: dict[str, Any] = res.json()
    return data


def create_order(amount: int, receipt: str, notes: dict[str, str]) -> dict[str, Any]:
    return _call("POST", "/orders", json={"amount": amount, "currency": "INR", "receipt": receipt, "notes": notes})


def order_payments(order_id: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = _call("GET", f"/orders/{order_id}/payments").get("items", [])
    return items


def _hmac(secret: str, message: bytes) -> str:
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def checkout_signature_ok(order_id: str, payment_id: str, signature: str) -> bool:
    """The signature Checkout hands the browser after a successful payment."""
    _, secret = _auth()
    return hmac.compare_digest(_hmac(secret, f"{order_id}|{payment_id}".encode()), signature)


def webhook_signature_ok(body: bytes, signature: str) -> bool:
    secret = settings.razorpay_webhook_secret
    return bool(secret) and hmac.compare_digest(_hmac(secret or "", body), signature or "")
