import uuid
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import transaction

from apps.orders.models import Order, OrderItem
from apps.payment.models import Payout


def split_amount(gross_kobo):
    """
    Returns (fee_kobo, net_kobo). The fee is rounded to a whole kobo and the
    net is whatever is left, so fee + net always equals gross exactly. That
    matters because the database rejects any payout where they don't add up.
    """
    percent = Decimal(str(settings.PLATFORM_COMMISSION_PERCENT))
    fee = (Decimal(gross_kobo) * percent / Decimal(100)).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
    fee_kobo = int(fee)
    return fee_kobo, gross_kobo - fee_kobo


@transaction.atomic
def create_payouts_for_order(order_id):
    """
    One Payout per merchant per order, in 'pending' status. Safe to call
    twice: the unique constraint plus get_or_create means a repeat creates
    nothing. Returns the IDs of the payouts created by THIS call.
    """
    order = Order.objects.get(id=order_id)
    if order.status != "completed":
        return []

    gross_by_merchant = defaultdict(int)
    items = OrderItem.objects.filter(order_id=order_id).select_related("product")
    for item in items:
        # unit_price is the snapshot taken at checkout, never the product's
        # current price. Converted to whole kobo before any arithmetic.
        line_kobo = int((item.unit_price * 100).to_integral_value()) * item.quantity
        gross_by_merchant[item.product.merchant_id] += line_kobo

    created_ids = []
    for merchant_id, gross_kobo in sorted(gross_by_merchant.items()):
        fee_kobo, net_kobo = split_amount(gross_kobo)
        payout, created = Payout.objects.get_or_create(
            order_id=order_id,
            merchant_id=merchant_id,
            defaults={
                "gross_kobo": gross_kobo,
                "fee_kobo": fee_kobo,
                "net_kobo": net_kobo,
                # Generated once and stored, so every retry of the transfer
                # reuses the same reference and can't pay twice.
                "reference": str(uuid.uuid4()),
            },
        )
        if created:
            created_ids.append(payout.id)
    return created_ids