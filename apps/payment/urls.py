from django.urls import path

from apps.payment.views import InitiatePaymentView, PaystackCallbackView, PaystackWebhookView

urlpatterns = [
    path("orders/<int:order_id>/initiate/", InitiatePaymentView.as_view(), name="initiate-payment"),
    path("webhook/paystack/", PaystackWebhookView.as_view(), name="paystack-webhook"),
    path("callback/", PaystackCallbackView.as_view(), name="paystack-callback"),  # Placeholder for now
]