from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.reviews.exceptions import (
    AlreadyReviewedError,
    OrderNotCompletedError,
    ReviewItemNotFoundError,
    SelfReviewError,
)
from apps.reviews.serializers import CreateReviewSerializer, ReviewSerializer
from apps.reviews.services import create_review
from django.db.models import Avg
from rest_framework import generics, permissions
from rest_framework.pagination import PageNumberPagination

from apps.reviews.models import Review

class ReviewPagination(PageNumberPagination):
    page_size = 20
    
class CreateReviewView(APIView):
    def post(self, request):
        serializer = CreateReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            review = create_review(
                request.user, data["order_item_id"], data["rating"], data.get("comment", "")
            )
        except ReviewItemNotFoundError:
            return Response(status=status.HTTP_404_NOT_FOUND)
        except OrderNotCompletedError as e:
            return Response(
                {"detail": f"You can only review items from completed orders (this one is {e.current_status})."},
                status=status.HTTP_409_CONFLICT,
            )
        except SelfReviewError:
            return Response(
                {"detail": "You cannot review your own product."},
                status=status.HTTP_403_FORBIDDEN,
            )
        except AlreadyReviewedError:
            return Response(
                {"detail": "You have already reviewed this item."},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(ReviewSerializer(review).data, status=status.HTTP_201_CREATED)

class MerchantReviewsView(generics.ListAPIView):
    serializer_class = ReviewSerializer
    permission_classes = [permissions.AllowAny]
    # Public endpoint: skip authentication entirely, so a stale or expired
    # token in the header can't turn a public read into a 401.
    authentication_classes = []
    pagination_class = ReviewPagination

    def get_queryset(self):
        return Review.objects.filter(
            order_item__product__merchant_id=self.kwargs["merchant_id"]
        ).select_related("order_item__product", "order_item__order__buyer")

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        # Computed over all of the merchant's reviews, not just this page.
        average = self.get_queryset().aggregate(avg=Avg("rating"))["avg"]
        response.data["average_rating"] = round(average, 2) if average is not None else None
        return response