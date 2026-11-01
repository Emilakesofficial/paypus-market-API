import hashlib
import hmac
import uuid

import requests
from django.conf import settings

PAYSTACK_BASE_URL = "https://api.paystack.co"
TEST_BANK_CODE = "001"


class AccountVerificationError(Exception):
    """The account couldn't be verified (wrong number or wrong bank)."""


class ProviderRateLimitedError(Exception):
    """Paystack is throttling us. The caller should say 'try again later'."""

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

def resolve_account(account_number, bank_code):
    """
    Ask Paystack who owns this account. Returns the account name, or None
    if it can't be resolved (wrong number or wrong bank). Network problems
    raise requests.RequestException instead, so "bad account" and
    "provider unreachable" are never confused with each other.
    """
    response = requests.get(
        f"{PAYSTACK_BASE_URL}/bank/resolve",
        headers={"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"},
        params={"account_number": account_number, "bank_code": bank_code},
        timeout=10,
    )
    if response.status_code == 429:
        raise ProviderRateLimitedError()
    if response.status_code in (400, 422):
        return None
    response.raise_for_status()
    return response.json()["data"]["account_name"]

def create_transfer_recipient(name, account_number, bank_code):
    """
    Create a transfer recipient. Returns the recipient code, or None if
    the account can't be resolved (wrong number or wrong bank). Network
    problems raise requests.RequestException instead, so "bad account" and
    "provider unreachable" are never confused with each other.
    """
    response = requests.post(
        f"{PAYSTACK_BASE_URL}/transferrecipient",
        headers={"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"},
        json={
            "type": "nuban",
            "name": name,
            "account_number": account_number,
            "bank_code": bank_code,
            "currency": "NGN",
        },
        timeout=10,
    )
    if response.status_code in (400, 422):
        return None
    response.raise_for_status()
    return response.json()["data"]

def verify_and_register_account(account_number, bank_code):
    """
    Returns (account_name, recipient_code, bank_name).
    Raises AccountVerificationError if the account can't be verified.
    Network problems raise requests.RequestException.
    """
    if bank_code == TEST_BANK_CODE:
        # Refused unless the dev flag is on AND a saved recipient exists.
        # This check runs before any network call.
        if not (settings.PAYSTACK_TEST_BANK_ENABLED and settings.PAYSTACK_TEST_RECIPIENT_CODE):
            raise AccountVerificationError()
        account_name = resolve_account(account_number, bank_code)
        if not account_name:
            raise AccountVerificationError()
        # Paystack can't create a recipient on the test bank, so reuse the
        # one we saved earlier.
        return account_name, settings.PAYSTACK_TEST_RECIPIENT_CODE, "Paystack Test Bank"

    account_name = resolve_account(account_number, bank_code)
    if not account_name:
        raise AccountVerificationError()
    recipient = create_transfer_recipient(account_name, account_number, bank_code)
    return account_name, recipient["recipient_code"], recipient["details"]["bank_name"]

def _safe_json(response):
    try:
        return response.json()
    except ValueError:
        return {}


def initiate_transfer(recipient_code, amount_kobo, reference, reason):
    """
    Returns (http_status, body). It never raises for an HTTP error status,
    only for network problems, so the caller can tell "Paystack said no"
    apart from "we don't know what happened".
    """
    if settings.PAYSTACK_FAKE_TRANSFERS:
        from apps.payment import fake_paystack
        return fake_paystack.initiate_transfer(recipient_code, amount_kobo, reference, reason)
    
    response = requests.post(
        f"{PAYSTACK_BASE_URL}/transfer",
        headers={"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"},
        json={
            "source": "balance",
            "amount": int(amount_kobo),
            "recipient": recipient_code,
            "reference": reference,
            "reason": reason,
            "currency": "NGN",
        },
        timeout=15,
    )
    return response.status_code, _safe_json(response)


def verify_transfer(reference):
    if settings.PAYSTACK_FAKE_TRANSFERS:
        from apps.payment import fake_paystack
        return fake_paystack.verify_transfer(reference)
    
    response = requests.get(
        f"{PAYSTACK_BASE_URL}/transfer/verify/{reference}",
        headers={"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"},
        timeout=15,
    )
    return response.status_code, _safe_json(response)