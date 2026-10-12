from django.db import models

from apps.orders.models import Order
from django.conf import settings


class Payment(models.Model):
    STATUS_CHOICES = [
        ("pending", "pending"),
        ("success", "success"),
        ("failed", "failed"),
    ]

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="payment")
    reference = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    amount_kobo = models.BigIntegerField()
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment({self.reference}, {self.status})"


class ProcessedWebhookEvent(models.Model):
    """
    Tracks Paystack event IDs already handled, so a retried webhook
    (Paystack resends on non-2xx or timeout) is recognized and skipped
    rather than reprocessed.
    """
    event_id = models.CharField(max_length=150, unique=True)
    processed_at = models.DateTimeField(auto_now_add=True)
    
class PayoutAccount(models.Model):
    """
    A merchant's payout destination. We keep Paystack's recipient code and
    just enough to show the merchant which account it is. The full account
    number is never stored.
    """
    merchant = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payout_account"
    )
    recipient_code = models.CharField(max_length=50)
    bank_name = models.CharField(max_length=100)
    account_name = models.CharField(max_length=150)
    account_last4 = models.CharField(max_length=4)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.merchant} -> {self.bank_name} ****{self.account_last4}"


class Payout(models.Model):
    STATUS_CHOICES = [
        ("pending", "pending"),        # created, no transfer started yet
        ("processing", "processing"),  # transfer requested, waiting on the webhook
        ("paid", "paid"),
        ("failed", "failed"),
    ]

    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="payouts")
    merchant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payouts"
    )
    gross_kobo = models.BigIntegerField()  # the merchant's items in this order
    fee_kobo = models.BigIntegerField()    # platform commission
    net_kobo = models.BigIntegerField()    # what the merchant receives
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="pending")
    reference = models.CharField(max_length=100, unique=True)  # sent to Paystack
    transfer_code = models.CharField(max_length=50, blank=True)
    failure_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            # One payout per merchant per order: a retry can't pay twice.
            models.UniqueConstraint(
                fields=["order", "merchant"], name="unique_payout_per_order_merchant"
            ),
            models.CheckConstraint(
                condition=models.Q(gross_kobo__gte=0, fee_kobo__gte=0, net_kobo__gte=0),
                name="payout_amounts_non_negative",
            ),
            # The three amounts can never disagree with each other.
            models.CheckConstraint(
                condition=models.Q(net_kobo=models.F("gross_kobo") - models.F("fee_kobo")),
                name="payout_net_equals_gross_minus_fee",
            ),
        ]

    def __str__(self):
        return f"Payout({self.reference}, {self.status})"