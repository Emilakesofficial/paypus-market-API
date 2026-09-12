from rest_framework import status
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.cart.models import Cart, CartItem
from apps.cart.serializers import AddCartItemSerializer, CartSerializer


class CartView(APIView):
    def get(self, request):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return Response(CartSerializer(cart).data)


class CartItemListView(APIView):
    def post(self, request):
        serializer = AddCartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = serializer.product
        quantity = serializer.validated_data["quantity"]

        cart, _ = Cart.objects.get_or_create(user=request.user)
        item, created = CartItem.objects.get_or_create(
            cart=cart, product=product, defaults={"quantity": quantity}
        )
        if not created:
            # Product already in cart — increment rather than duplicate,
            # and re-check total quantity against current stock.
            new_quantity = item.quantity + quantity
            if new_quantity > product.stock_quantity:
                return Response(
                    {"quantity": f"Only {product.stock_quantity} in stock."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            item.quantity = new_quantity
            item.save()

        return Response(CartSerializer(cart).data, status=status.HTTP_201_CREATED)


class CartItemDetailView(APIView):
    def get_item(self, request, item_id):
        # Scoped to the logged-in user's own cart — someone else's
        # cart item ID simply doesn't exist from this user's perspective,
        # rather than existing-but-forbidden. Avoids leaking existence.
        return get_object_or_404(CartItem, id=item_id, cart__user=request.user)

    def patch(self, request, item_id):
        item = self.get_item(request, item_id)
        quantity = request.data.get("quantity")
        if quantity is None or int(quantity) < 1:
            return Response({"quantity": "Must be a positive integer."}, status=status.HTTP_400_BAD_REQUEST)
        if int(quantity) > item.product.stock_quantity:
            return Response(
                {"quantity": f"Only {item.product.stock_quantity} in stock."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        item.quantity = quantity
        item.save()
        return Response(CartSerializer(item.cart).data)

    def delete(self, request, item_id):
        item = self.get_item(request, item_id)
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)