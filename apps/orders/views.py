from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from ..cart.models import Cart
from .exceptions import EmptyCartError, InsufficientStockError
from .models import Order
from .serializers import OrderSerializer
from .services import create_order_from_cart


class CheckoutView(APIView):
    def post(self, request):
        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            return Response(
                {"detail": "Idempotency-Key header is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Repeat request with the same key returns the existing order —
        # never creates a second one. Checked before touching the cart at all.
        existing = Order.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return Response(OrderSerializer(existing).data, status=status.HTTP_200_OK)

        cart, _ = Cart.objects.get_or_create(user=request.user)

        try:
            order = create_order_from_cart(request.user, cart, idempotency_key)
        except EmptyCartError:
            return Response({"detail": "Your cart is empty."}, status=status.HTTP_400_BAD_REQUEST)
        except InsufficientStockError as e:
            return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)

        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


class OrderDetailView(APIView):
    def get(self, request, order_id):
        order = Order.objects.filter(id=order_id, buyer=request.user).first()
        if not order:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(OrderSerializer(order).data)