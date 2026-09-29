from django.db import models

from apps.orders.models import Order


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