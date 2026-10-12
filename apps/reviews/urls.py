from django.urls import path

from apps.reviews.views import CreateReviewView, MerchantReviewsView

urlpatterns = [
    path("", CreateReviewView.as_view(), name="review-create"),
    path("merchant/<int:merchant_id>/", MerchantReviewsView.as_view(), name="merchant-reviews"),
]