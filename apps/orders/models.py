import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.catalog.models import Product


class Order(models.Model):
    STATUS_CHOICES = [
        ("pending_payment", "pending_payment"),
        ("paid", "paid"),
        ("shipped", "shipped"),
        ("completed", "completed"),
        ("cancelled", "cancelled"),
        ("refunded", "refunded"),
    ]

    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending_payment")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    idempotency_key = models.CharField(max_length=100, unique=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order #{self.id} ({self.status})"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)  # snapshot, never re-read later

    def __str__(self):
        return f"{self.quantity} x {self.product.name} @ {self.unit_price}"


def default_expiry():
    return timezone.now() + timedelta(minutes=20)