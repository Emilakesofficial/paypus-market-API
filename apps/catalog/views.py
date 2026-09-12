from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, viewsets

from apps.catalog.models import Product
from apps.catalog.permissions import IsMerchantOwnerOrReadOnly
from apps.catalog.serializers import ProductSerializer


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsMerchantOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["status"]
    search_fields = ["name", "sku"]

    def perform_create(self, serializer):
        serializer.save(merchant=self.request.user)