from django.conf import settings
from django.db import models


class Product(models.Model):
    STATUS_CHOICES = [
        ("active", "active"),
        ("inactive", "inactive"),
    ]

    merchant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="products"
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock_quantity = models.PositiveIntegerField(default=0)
    sku = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(stock_quantity__gte=0), name="catalog_stock_non_negative"
            )
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.sku})"