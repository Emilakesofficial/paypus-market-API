from django.db import models

from apps.orders.models import Order


class Invoice(models.Model):
    # PROTECT, not CASCADE: an invoice is a financial record and
    # shouldn't silently disappear if an order is ever deleted.
    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name="invoice")
    invoice_number = models.CharField(max_length=30, unique=True)
    pdf_file = models.FileField(upload_to="invoices/", blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.invoice_number

    @staticmethod
    def number_for(order):
        # Derived from the order, so the number is stable and can never
        # collide. Generating an invoice twice for one order can't produce
        # two different numbers.
        return f"INV-{order.created_at.year}-{order.id:06d}"