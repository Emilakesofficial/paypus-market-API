from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path("", include("apps.common.urls")),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.catalog.urls")),
    path("api/v1/cart/", include("apps.cart.urls")),
    path("api-auth/", include("rest_framework.urls")),
]
