from django.http import FileResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.invoices.models import Invoice


class InvoiceDownloadView(APIView):
    def get(self, request, order_id):
        # Scoped to the buyer: anyone else gets the same 404 as a missing
        # invoice, so existence isn't leaked.
        invoice = Invoice.objects.filter(
            order_id=order_id, order__buyer=request.user
        ).first()
        if not invoice or not invoice.pdf_file:
            return Response(
                {"detail": "Invoice not available."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return FileResponse(
            invoice.pdf_file.open("rb"),
            content_type="application/pdf",
            as_attachment=True,
            filename=f"{invoice.invoice_number}.pdf",
        )