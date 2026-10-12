from django.contrib import admin

from apps.payment.models import Payment, ProcessedWebhookEvent


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["reference", "order", "status", "amount_kobo", "paid_at"]
    list_filter = ["status"]


@admin.register(ProcessedWebhookEvent)
class ProcessedWebhookEventAdmin(admin.ModelAdmin):
    list_display = ["event_id", "processed_at"]
    
from apps.payment.models import Payout, PayoutAccount


@admin.register(PayoutAccount)
class PayoutAccountAdmin(admin.ModelAdmin):
    list_display = ["merchant", "bank_name", "account_name", "account_last4"]


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ["reference", "order", "merchant", "net_kobo", "status"]
    list_filter = ["status"]