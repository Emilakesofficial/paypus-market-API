from django.urls import path

from apps.cart.views import CartItemDetailView, CartItemListView, CartView

urlpatterns = [
    path("", CartView.as_view(), name="cart-detail"),
    path("items/", CartItemListView.as_view(), name="cart-item-add"),
    path("items/<int:item_id>/", CartItemDetailView.as_view(), name="cart-item-detail"),
]