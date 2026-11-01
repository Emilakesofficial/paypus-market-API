from datetime import timedelta
from django.utils import timezone

from django.db import transaction
from django.db.models import F

from .models import Product
from .models import Order, OrderItem

from django.utils import timezone

from apps.orders.exceptions import (
    EmptyCartError,
    InsufficientStockError,
    NothingToShipError,
    OrderNotFoundError,
    OrderNotShippableError,
    OrderNotConfirmableError
)
from apps.invoices.tasks import generate_invoice
from apps.payment.payouts import create_payouts_for_order
from apps.payment.tasks import send_payout


expires_at = timezone.now() + timedelta(minutes=30)

def reserve_stock(product_id, quantity):
    """
    Single conditional UPDATE — atomic at the database level.
    No read-then-write in Python, so two concurrent calls on the same
    row can't both pass a stock check before either decrements.
    """
    updated = Product.objects.filter(
        id=product_id, stock_quantity__gte=quantity
    ).update(stock_quantity=F("stock_quantity") - quantity)
    return updated > 0


@transaction.atomic
def create_order_from_cart(user, cart, idempotency_key):
    items = list(cart.items.select_related("product").all())
    if not items:
        raise EmptyCartError()

    # Lock/reserve products in a consistent order (sorted by product ID)
    # so two checkouts sharing products can't deadlock against each other.
    items.sort(key=lambda i: i.product_id)

    order_items_data = []
    total = 0
    for item in items:
        product = item.product
        unit_price = product.price  # snapshot before reservation
        if not reserve_stock(product.id, item.quantity):
            # Transaction rolls back — any earlier reservations in this
            # loop are undone automatically, nothing is left half-reserved.
            raise InsufficientStockError(product.name)
        order_items_data.append((product, item.quantity, unit_price))
        total += unit_price * item.quantity

    order = Order.objects.create(
        buyer=user,
        total_amount=total,
        idempotency_key=idempotency_key,
        expires_at=expires_at,
    )
    OrderItem.objects.bulk_create([
        OrderItem(order=order, product=product, quantity=quantity, unit_price=unit_price)
        for product, quantity, unit_price in order_items_data
    ])
    cart.items.all().delete()
    return order

@transaction.atomic
def ship_order_items(order_id, merchant):
    # Lock the order row so two merchants shipping at the same moment are
    # serialized. Without this, each could see the other's items as still
    # unshipped, and neither would flip the order to "shipped".
    order = Order.objects.select_for_update().filter(id=order_id).first()
    merchant_items = OrderItem.objects.filter(order_id=order_id, product__merchant=merchant)

    # Same 404 whether the order doesn't exist or it has none of this
    # merchant's items, so existence isn't leaked to unrelated merchants.
    if not order or not merchant_items.exists():
        raise OrderNotFoundError()

    if order.status != "paid":
        raise OrderNotShippableError(order.status)

    shipped_count = merchant_items.filter(shipped_at__isnull=True).update(
        shipped_at=timezone.now()
    )
    if shipped_count == 0:
        raise NothingToShipError()

    # If every item in the order has now shipped, the order is shipped.
    if not OrderItem.objects.filter(order_id=order_id, shipped_at__isnull=True).exists():
        Order.objects.filter(id=order_id, status="paid").update(status="shipped")

    order.refresh_from_db()
    return order, shipped_count

@transaction.atomic
def confirm_delivery(order_id, buyer):
    # Scoped to the buyer, so anyone else gets the same "not found"
    # as a nonexistent order.
    if not Order.objects.filter(id=order_id, buyer=buyer).exists():
        raise OrderNotFoundError()

    # Conditional update: only moves to completed if currently shipped.
    updated = Order.objects.filter(
        id=order_id, buyer=buyer, status="shipped"
    ).update(status="completed")

    order = Order.objects.get(id=order_id)
    if not updated:
        raise OrderNotConfirmableError(order.status)

    payout_ids = create_payouts_for_order(order_id)
    for payout_id in payout_ids:
        # on_commit runs only if the whole transaction succeeds, so a payout
        # is never sent for an order whose completion got rolled back.
        # `pid=payout_id` pins this loop's value: without it, every lambda
        # would see the last payout_id by the time they run.
        transaction.on_commit(lambda pid=payout_id: send_payout.delay(pid))
    return order