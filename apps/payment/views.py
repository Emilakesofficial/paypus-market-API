import requests
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from django.conf import settings

from apps.orders.models import Order
from apps.payment.models import Payment, PayoutAccount
from django.db import transaction as db_transaction
from django.utils import timezone

from apps.payment.models import ProcessedWebhookEvent, PayoutAccount, Payout
from apps.payment.service import (
    verify_transaction, verify_webhook_signature, generate_reference, 
    initialize_transaction, create_transfer_recipient, resolve_account,
)
from apps.payment.serializers import PayoutAccountInputSerializer, PayoutAccountSerializer
from apps.payment.service import (
    AccountVerificationError, ProviderRateLimitedError,
    verify_and_register_account
)
from apps.payment.tasks import send_payout

import logging

logger = logging.getLogger(__name__)

class InitiatePaymentView(APIView):
    def post(self, request, order_id):
        order = Order.objects.filter(id=order_id, buyer=request.user).first()
        if not order:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if order.status != "pending_payment":
            return Response(
                {"detail": f"Order is not payable in its current status ({order.status})."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Idempotent in its own right — if a Payment already exists for
        # this order (e.g. user refreshed the checkout page), reuse it
        # rather than initializing a second Paystack transaction.
        existing_payment = getattr(order, "payment", None)
        if existing_payment and existing_payment.status == "pending":
            return Response({"reference": existing_payment.reference})

        amount_kobo = int(order.total_amount * 100)
        reference = generate_reference(order)

        data = initialize_transaction(
            email=request.user.email,
            amount_kobo=amount_kobo,
            reference=reference,
            callback_url=(settings.CALLBACK_URL)
        )

        Payment.objects.create(order=order, reference=reference, amount_kobo=amount_kobo)

        return Response({
            "authorization_url": data["authorization_url"],
            "reference": reference,
        })

class PaystackWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        signature = request.headers.get("X-Paystack-Signature")
        
        if not verify_webhook_signature(request.body, signature):
            return Response({"detail": "Invalid signature"}, status=status.HTTP_401_UNAUTHORIZED)

        payload = request.data
        event_type = payload.get("event")
        reference = payload.get("data", {}).get("reference")

        if event_type != "charge.success" or not reference:
            # Acknowledge anything we don't care about so Paystack
            # doesn't keep retrying it.
            return Response(status=status.HTTP_200_OK)

        event_id = f"{event_type}:{reference}"
        
        _, created = ProcessedWebhookEvent.objects.get_or_create(event_id=event_id)
        if not created:
            return Response(status=status.HTTP_200_OK)  # already handled, safe no-op

        # Never trust the webhook payload's amount/status directly —
        # confirm against Paystack's own records first.
        verified = verify_transaction(reference)
        if verified["status"] != "success":
            return Response({"detail": "Transaction not successful"}, status=status.HTTP_200_OK)

        payment = Payment.objects.filter(reference=reference).first()
        if not payment:
            return Response(status=status.HTTP_200_OK)

        if verified["amount"] != payment.amount_kobo:
            # Amount mismatch — don't silently mark as paid. Worth logging
            # loudly in a real system; for now this just refuses to proceed.
            return Response(status=status.HTTP_200_OK)

        with db_transaction.atomic():
            payment.status = "success"
            payment.paid_at = timezone.now()
            payment.save(update_fields=["status", "paid_at"])

            # Conditional update — only transitions if still pending_payment.
            # If the expiry task or a manual verify already moved it,
            # this becomes a safe no-op instead of double-processing.
            order = Order.objects.filter(
                id=payment.order_id, status="pending_payment"
            ).updated(status="paid")

        return Response(status=status.HTTP_200_OK)
    
class PaystackCallbackView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        reference = request.query_params.get("reference")

        if not reference:
            return Response(
                {"detail": "Missing reference"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verify with Paystack rather than trusting query params.
        verified = verify_transaction(reference)

        return Response({
            "reference": reference,
            "status": verified["status"],
        })
        
class PayoutAccountView(APIView):
    def get(self, request):
        account = PayoutAccount.objects.filter(merchant=request.user).first()
        if not account:
            return Response({"detail": "No payout account set."}, status=status.HTTP_404_NOT_FOUND)
        return Response(PayoutAccountSerializer(account).data)

    def put(self, request):
        serializer = PayoutAccountInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account_number = serializer.validated_data["account_number"]
        bank_code = serializer.validated_data["bank_code"]

        try:
            account_name, recipient_code, bank_name = verify_and_register_account(
                account_number, bank_code
            )
        except AccountVerificationError:
            return Response(
                {"detail": "We couldn't verify that account. Check the account number and bank."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ProviderRateLimitedError:
            logger.warning("Paystack rate-limited the account lookup")
            return Response(
                {"detail": "Account verification is temporarily unavailable. Please try again later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except requests.RequestException:
            logger.exception("Paystack payout account setup failed")
            return Response(
                {"detail": "Couldn't reach the payment provider. Please try again."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        account, _ = PayoutAccount.objects.update_or_create(
            merchant=request.user,
            defaults={
                "recipient_code": recipient_code,
                "bank_name": bank_name,
                "account_name": account_name,
                "account_last4": account_number[-4:],
            },
        )
        # Any payouts that were waiting for a destination can go out now.
        # Queuing one twice is harmless: the task claims each payout
        # atomically, so only one worker ever sends it.
        waiting_ids = list(
            Payout.objects.filter(merchant=request.user, status="pending")
            .values_list("id", flat=True)
        )
        try:
            for payout_id in waiting_ids:
                send_payout.delay(payout_id)
        except Exception:
            # The account is saved. If the queue is down, the payouts stay
            # pending and the reconciliation sweeper (next step) picks them up.
            logger.exception("Could not queue waiting payouts for merchant %s", request.user.id)
        return Response(PayoutAccountSerializer(account).data)