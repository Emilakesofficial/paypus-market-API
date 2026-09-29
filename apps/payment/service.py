import hashlib
import hmac
import uuid

import requests
from django.conf import settings

PAYSTACK_BASE_URL = "https://api.paystack.co"


def initialize_transaction(email, amount_kobo, reference, callback_url):
    response = requests.post(
        f"{PAYSTACK_BASE_URL}/transaction/initialize",
        headers={"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"},
        json={
            "email": email,
            "amount": amount_kobo,
            "reference": reference,
            "callback_url": callback_url,
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["data"]


def verify_transaction(reference):
    """
    Always call this before trusting a webhook's payload — the webhook
    tells you *that* something happened, this confirms *what* actually
    happened, straight from Paystack's records.
    """
    response = requests.get(
        f"{PAYSTACK_BASE_URL}/transaction/verify/{reference}",
        headers={"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["data"]


def verify_webhook_signature(request_body, signature_header):
    expected = hmac.new(
        settings.PAYSTACK_SECRET_KEY.encode(),
        request_body,
        hashlib.sha512,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header or "")

def generate_reference(order):
    return f"paypus-{order.id}-{uuid.uuid4().hex[:10]}"