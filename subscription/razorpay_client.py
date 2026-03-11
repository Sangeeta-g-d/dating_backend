from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any, Dict

import razorpay
from django.conf import settings

logger = logging.getLogger(__name__)


def get_client() -> razorpay.Client:
    """
    Return a configured Razorpay client instance.

    Raises RuntimeError if keys are not configured to avoid silently
    running payment flows without proper credentials.
    """
    key_id = settings.RAZORPAY_KEY_ID
    key_secret = settings.RAZORPAY_KEY_SECRET

    if not key_id or not key_secret:
        raise RuntimeError("Razorpay keys are not configured")

    return razorpay.Client(auth=(key_id, key_secret))


def create_order(amount_paise: int, currency: str, notes: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a Razorpay order for the given amount.
    Amount must be in paise for INR (i.e. rupees * 100).
    """
    client = get_client()
    logger.info("Creating Razorpay order", extra={"amount_paise": amount_paise, "currency": currency, "notes": notes})
    return client.order.create(
        {
            "amount": amount_paise,
            "currency": currency,
            "payment_capture": 1,
            "notes": notes,
        }
    )


def fetch_payment(payment_id: str) -> Dict[str, Any]:
    """Fetch payment details from Razorpay."""
    client = get_client()
    return client.payment.fetch(payment_id)


def verify_payment_signature(
    razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str
) -> bool:
    """
    Verify the Razorpay payment signature from Checkout callback.
    Uses HMAC SHA256 with the API secret as per Razorpay docs.
    """
    key_secret = settings.RAZORPAY_KEY_SECRET
    if not key_secret:
        logger.error("RAZORPAY_KEY_SECRET is not configured for signature verification")
        return False

    message = f"{razorpay_order_id}|{razorpay_payment_id}".encode()
    generated_signature = hmac.new(key_secret.encode(), message, hashlib.sha256).hexdigest()

    is_valid = hmac.compare_digest(generated_signature, razorpay_signature)
    if not is_valid:
        logger.warning(
            "Invalid Razorpay payment signature",
            extra={
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": razorpay_payment_id,
            },
        )
    return is_valid


def verify_webhook_signature(payload: bytes, received_signature: str) -> bool:
    """
    Verify Razorpay webhook signature using the webhook secret.
    """
    secret = settings.RAZORPAY_WEBHOOK_SECRET
    if not secret:
        logger.error("RAZORPAY_WEBHOOK_SECRET is not configured for webhook verification")
        return False

    generated = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    is_valid = hmac.compare_digest(generated, received_signature)
    if not is_valid:
        logger.warning("Invalid Razorpay webhook signature")
    return is_valid

