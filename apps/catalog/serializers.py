from rest_framework import serializers

from apps.catalog.models import Product


class ProductSerializer(serializers.ModelSerializer):
    merchant = serializers.ReadOnlyField(source="merchant.username")

    class Meta:
        model = Product
        fields = [
            "id", "merchant", "name", "description", "price",
            "stock_quantity", "sku", "status", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "merchant", "created_at", "updated_at"]