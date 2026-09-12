from rest_framework import permissions


class IsMerchantOwnerOrReadOnly(permissions.BasePermission):
    """
    Anyone can view (list/retrieve). Only the product's owning merchant
    can update or delete it. Creation is handled separately — it just
    requires being authenticated at all (see IsAuthenticatedOrReadOnly
    on the viewset).
    """

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.merchant_id == request.user.id