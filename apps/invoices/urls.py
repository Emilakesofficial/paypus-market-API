from django.urls import path

from apps.invoices.views import InvoiceDownloadView

urlpatterns = [
    path("order/<int:order_id>/", InvoiceDownloadView.as_view(), name="invoice-download"),
]