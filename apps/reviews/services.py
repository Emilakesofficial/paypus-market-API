from django.db import IntegrityError, transaction

from apps.orders.models import OrderItem
from apps.reviews.exceptions import (
    AlreadyReviewedError,
    OrderNotCompletedError,
    ReviewItemNotFoundError,
    SelfReviewError,
)
from apps.reviews.models import Review


def create_review(buyer, order_item_id, rating, comment):
    # Scoped to the buyer, so someone else's item looks exactly like a
    # nonexistent one.
    item = (
        OrderItem.objects.select_related("order", "product")
        .filter(id=order_item_id, order__buyer=buyer)
        .first()
    )
    if not item:
        raise ReviewItemNotFoundError()

    if item.order.status != "completed":
        raise OrderNotCompletedError(item.order.status)

    # Without this, a merchant could buy their own product and review it.
    if item.product.merchant_id == buyer.id:
        raise SelfReviewError()

    try:
        with transaction.atomic():
            return Review.objects.create(order_item=item, rating=rating, comment=comment)
    except IntegrityError:
        # The OneToOne on order_item rejected a second review. Relying on
        # the constraint instead of a "does one exist?" check means two
        # simultaneous submissions can't both get through. The rating is
        # already validated by the serializer, so a unique violation is the
        # only thing that can land here.
        raise AlreadyReviewedError()