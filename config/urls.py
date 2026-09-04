from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path("", include("apps.common.urls")),
    path("api/v1/auth/", include("apps.accounts.urls")),
]
