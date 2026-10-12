from celery import shared_task
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.catalog.models import Product
from apps.orders.models import Order, OrderItem


@shared_task
def cancel_expired_orders():
    expired_ids = list(
        Order.objects.filter(status="pending_payment", expires_at__lt=timezone.now())
        .values_list("id", flat=True)
    )

    cancelled = 0
    for order_id in expired_ids:
        with transaction.atomic():
            # Conditional update: only cancel if the order is STILL
            # pending_payment. If a payment webhook marked it paid between
            # our query above and this line, updated == 0 and we skip it.
            updated = Order.objects.filter(
                id=order_id, status="pending_payment"
            ).update(status="cancelled")
            if not updated:
                continue

            # Only restock if we actually won the transition, so stock
            # is never returned for an order that got paid.
            items = OrderItem.objects.filter(order_id=order_id).order_by("product_id")
            for item in items:
                Product.objects.filter(id=item.product_id).update(
                    stock_quantity=F("stock_quantity") + item.quantity
                )
            cancelled += 1

    return cancelled