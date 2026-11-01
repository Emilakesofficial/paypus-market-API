"""
A stand-in for Paystack's transfer endpoints, used only in development
(PAYSTACK_FAKE_TRANSFERS). Paystack's test mode always reports success, so
this is the only way to exercise failures, lost replies and retries.

State lives in the Django cache (Redis), so a later "verify" can see an
earlier "initiate", just like the real service, even across processes.
"""
import uuid

import requests
from django.core.cache import cache

_TRANSFER_KEY = "fake-paystack:transfer:{}"
_NEXT_OUTCOME_KEY = "fake-paystack:next-outcome"

OUTCOMES = ("success", "pending", "reject", "ratelimit", "timeout_before", "timeout_after")


def set_next_outcome(outcome):
    """Make the NEXT initiate call behave this way (one shot)."""
    assert outcome in OUTCOMES, outcome
    cache.set(_NEXT_OUTCOME_KEY, outcome, timeout=600)


def initiate_transfer(recipient_code, amount_kobo, reference, reason):
    outcome = cache.get(_NEXT_OUTCOME_KEY, "success")
    cache.delete(_NEXT_OUTCOME_KEY)

    if outcome == "timeout_before":
        # The request never reached Paystack.
        raise requests.ConnectionError("fake: connection dropped before Paystack saw it")
    if outcome == "ratelimit":
        return 429, {"status": False, "message": "fake: too many requests"}
    if outcome == "reject":
        return 400, {"status": False, "message": "fake: insufficient balance"}

    if cache.get(_TRANSFER_KEY.format(reference)):
        # Mirrors Paystack's documented error for a reused reference.
        return 400, {
            "status": False,
            "message": "fake: reference has already been used on a prior transfer",
        }

    transfer = {
        "reference": reference,
        "amount": int(amount_kobo),
        "recipient": recipient_code,
        "reason": reason,
        "currency": "NGN",
        "status": "pending" if outcome == "pending" else "success",
        "transfer_code": "TRF_fake" + uuid.uuid4().hex[:10],
    }
    cache.set(_TRANSFER_KEY.format(reference), transfer, timeout=86400)

    if outcome == "timeout_after":
        # Paystack DID accept it, but the reply never reached us.
        raise requests.ConnectionError("fake: reply lost after Paystack accepted the transfer")
    return 200, {"status": True, "message": "Transfer has been queued", "data": transfer}


def verify_transfer(reference):
    transfer = cache.get(_TRANSFER_KEY.format(reference))
    if not transfer:
        return 404, {"status": False, "message": "Transfer not found"}
    return 200, {"status": True, "message": "Transfer retrieved", "data": transfer}