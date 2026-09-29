from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.orders.models import Order
from apps.payment.models import Payment
from django.db import transaction as db_transaction
from django.utils import timezone

from apps.payment.models import ProcessedWebhookEvent
from apps.payment.service import verify_transaction, verify_webhook_signature

from apps.payment.service import generate_reference, initialize_transaction


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
            callback_url="http://localhost:8000/api/payments/callback/",  # placeholder for now
        )

        Payment.objects.create(order=order, reference=reference, amount_kobo=amount_kobo)

        return Response({
            "authorization_url": data["authorization_url"],
            "reference": reference,
        })
        
class PaystackWebhookView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        signature = request.headers.get("X-Paystack-Signature")
        if not verify_webhook_signature(request.body, signature):
            return Response(status=status.HTTP_401_UNAUTHORIZED)

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
            return Response(status=status.HTTP_200_OK)

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
            payment.save()

            # Conditional update — only transitions if still pending_payment.
            # If the expiry task or a manual verify already moved it,
            # this becomes a safe no-op instead of double-processing.
            updated = Order.objects.filter(
                id=payment.order_id, status="pending_payment"
            ).update(status="paid")

        return Response(status=status.HTTP_200_OK)