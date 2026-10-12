from rest_framework import serializers

from apps.reviews.models import Review


class CreateReviewSerializer(serializers.Serializer):
    order_item_id = serializers.IntegerField()
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class ReviewSerializer(serializers.ModelSerializer):
    product_name = serializers.ReadOnlyField(source="order_item.product.name")
    reviewer = serializers.ReadOnlyField(source="order_item.order.buyer.username")

    class Meta:
        model = Review
        fields = ["id", "order_item", "product_name", "reviewer", "rating", "comment", "created_at"]