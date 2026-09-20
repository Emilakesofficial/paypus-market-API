from django.urls import path

from apps.orders.views import CheckoutView, OrderDetailView

urlpatterns = [
    path("checkout/", CheckoutView.as_view(), name="checkout"),
    path("<int:order_id>/", OrderDetailView.as_view(), name="order-detail"),
]