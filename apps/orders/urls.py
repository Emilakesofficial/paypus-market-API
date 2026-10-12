from django.urls import path

from apps.orders.views import CheckoutView, OrderDetailView, ShipOrderView, ConfirmDeliveryView

urlpatterns = [
    path("checkout/", CheckoutView.as_view(), name="checkout"),
    path("<int:order_id>/", OrderDetailView.as_view(), name="order-detail"),
    path("<int:order_id>/ship/", ShipOrderView.as_view(), name="order-ship"),
    path("<int:order_id>/confirm/", ConfirmDeliveryView.as_view(), name="order-confirm"),
]