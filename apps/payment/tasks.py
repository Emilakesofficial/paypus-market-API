import logging

import requests
from celery import shared_task
from django.utils import timezone

from apps.payment.models import Payout, PayoutAccount
from apps.payment.service import initiate_transfer, verify_transfer

logger = logging.getLogger(__name__)

# Statuses where Paystack understood the request and refused it.
# Anything else (429, 5xx, auth problems) means "try again later".
DEFINITE_REJECTIONS = (400, 422)
RETRY_DELAY_SECONDS = 60


def _record_transfer(payout_id, data):
    """Apply what Paystack says about a transfer to our Payout row."""
    transfer_status = data.get("status")
    fields = {"transfer_code": data.get("transfer_code", ""), "updated_at": timezone.now()}
    if transfer_status == "success":
        fields["status"] = "paid"
    elif transfer_status in ("failed", "reversed"):
        fields["status"] = "failed"
        fields["failure_reason"] = f"Paystack reported {transfer_status}"
    elif transfer_status == "otp":
        fields["status"] = "failed"
        fields["failure_reason"] = "Paystack is waiting for an OTP: turn off transfer confirmation"
    # "pending" or anything unrecognised: stay 'processing'; the transfer
    # webhook (a later step) delivers the final result.

    # Conditional: only touches the row if it is still 'processing', so a
    # webhook that already finalised it is never overwritten.
    Payout.objects.filter(id=payout_id, status="processing").update(**fields)


@shared_task(bind=True, max_retries=5)
def send_payout(self, payout_id, resume=False):
    payout = Payout.objects.get(id=payout_id)

    account = PayoutAccount.objects.filter(merchant_id=payout.merchant_id).first()
    if not account:
        # Nothing claimed: the payout stays pending until the merchant adds
        # a payout account.
        return "waiting for payout account"

    if resume:
        # An earlier attempt of this task already claimed the payout.
        if payout.status != "processing" or payout.transfer_code:
            return "nothing to resume"
        try:
            status_code, body = verify_transfer(payout.reference)
        except requests.RequestException as exc:
            raise self.retry(
                exc=exc, kwargs={"payout_id": payout_id, "resume": True},
                countdown=RETRY_DELAY_SECONDS,
            )
        if status_code == 200:
            # Paystack already has this transfer: adopt it, never send again.
            _record_transfer(payout_id, body.get("data") or {})
            return "adopted existing transfer"
        if status_code != 404:
            raise self.retry(
                kwargs={"payout_id": payout_id, "resume": True},
                countdown=RETRY_DELAY_SECONDS,
            )
        # 404: Paystack has never seen this reference, so sending is safe.
    else:
        claimed = Payout.objects.filter(id=payout_id, status="pending").update(
            status="processing", updated_at=timezone.now()
        )
        if not claimed:
            return "already claimed"

    try:
        status_code, body = initiate_transfer(
            recipient_code=account.recipient_code,
            amount_kobo=payout.net_kobo,
            reference=payout.reference,
            reason=f"Paypus payout for order #{payout.order_id}",
        )
    except requests.RequestException as exc:
        # Outcome unknown: Paystack may have received it. Stay 'processing'
        # and retry in resume mode, which checks the reference first.
        raise self.retry(
            exc=exc, kwargs={"payout_id": payout_id, "resume": True},
            countdown=RETRY_DELAY_SECONDS,
        )

    if status_code in (200, 201):
        _record_transfer(payout_id, body.get("data") or {})
        return "initiated"

    if status_code in DEFINITE_REJECTIONS:
        reason = (body.get("message") or "Rejected by Paystack")[:255]
        Payout.objects.filter(id=payout_id, status="processing").update(
            status="failed", failure_reason=reason, updated_at=timezone.now()
        )
        logger.warning("Payout %s rejected by Paystack: %s", payout_id, reason)
        return "rejected"

    raise self.retry(
        kwargs={"payout_id": payout_id, "resume": True},
        countdown=RETRY_DELAY_SECONDS,
    )