from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.orders.models import OrderItem


class Review(models.Model):
    # One review per purchased line item. The OneToOne is enforced by the
    # database, so two simultaneous submissions can't both succeed.
    order_item = models.OneToOneField(OrderItem, on_delete=models.CASCADE, related_name="review")
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(rating__gte=1, rating__lte=5),
                name="reviews_rating_1_to_5",
            )
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"Review({self.order_item_id}, {self.rating}/5)"