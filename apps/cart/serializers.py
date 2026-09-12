from rest_framework import serializers

from apps.cart.models import Cart, CartItem
from apps.catalog.models import Product


class CartItemSerializer(serializers.ModelSerializer):
    product_name = serializers.ReadOnlyField(source="product.name")
    unit_price = serializers.DecimalField(source="product.price", max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = ["id", "product", "product_name", "unit_price", "quantity"]


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ["id", "items", "total", "updated_at"]

    def get_total(self, obj):
        return sum(item.product.price * item.quantity for item in obj.items.all())


class AddCartItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)

    def validate_product_id(self, value):
        try:
            product = Product.objects.get(id=value, status="active")
        except Product.DoesNotExist:
            raise serializers.ValidationError("Product not found or unavailable.")
        self.product = product
        return value

    def validate(self, attrs):
        if attrs["quantity"] > self.product.stock_quantity:
            raise serializers.ValidationError(
                {"quantity": f"Only {self.product.stock_quantity} in stock."}
            )
        return attrs