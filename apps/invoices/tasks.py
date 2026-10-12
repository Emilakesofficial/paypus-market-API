from celery import shared_task
from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from django.utils import timezone

from apps.invoices.models import Invoice
from apps.orders.models import Order


@shared_task
def generate_invoice(order_id):
    order = Order.objects.select_related("buyer").get(id=order_id)

    # Only completed orders get an invoice.
    if order.status != "completed":
        return None

    # get_or_create plus the OneToOne constraint make this safe to retry:
    # running the task twice never creates a second invoice.
    invoice, _ = Invoice.objects.get_or_create(
        order=order,
        defaults={"invoice_number": Invoice.number_for(order)},
    )
    if invoice.pdf_file:
        return invoice.invoice_number  # already generated

    items = list(order.items.select_related("product__merchant"))
    lines = [
        {
            "name": item.product.name,
            "merchant": item.product.merchant.username,
            "quantity": item.quantity,
            # The snapshot taken at checkout, never the product's current price.
            "unit_price": item.unit_price,
            "line_total": item.unit_price * item.quantity,
        }
        for item in items
    ]

    html = render_to_string("invoices/invoice.html", {
        "invoice_number": invoice.invoice_number,
        "issued_on": timezone.now(),
        "order": order,
        "buyer_name": order.buyer.get_full_name() or order.buyer.username,
        "currency": items[0].product.currency if items else "NGN",
        "lines": lines,
    })
    from weasyprint import HTML
    pdf_bytes = HTML(string=html).write_pdf()
    invoice.pdf_file.save(f"{invoice.invoice_number}.pdf", ContentFile(pdf_bytes))
    return invoice.invoice_number