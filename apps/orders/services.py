from datetime import timedelta
from django.utils import timezone

from django.db import transaction
from django.db.models import F

from .models import Product
from .exceptions import EmptyCartError, InsufficientStockError
from .models import Order, OrderItem

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