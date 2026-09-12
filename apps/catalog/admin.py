from django.contrib import admin

from apps.catalog.models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "sku", "merchant", "price", "stock_quantity", "status"]
    list_filter = ["status"]
    search_fields = ["name", "sku"]