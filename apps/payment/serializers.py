from rest_framework import serializers

from apps.payment.models import PayoutAccount


class PayoutAccountInputSerializer(serializers.Serializer):
    account_number = serializers.RegexField(
        r"^\d{10}$", error_messages={"invalid": "Must be a 10-digit account number."}
    )
    bank_code = serializers.CharField(max_length=20)


class PayoutAccountSerializer(serializers.ModelSerializer):
    # Deliberately no recipient_code: it's an internal handle for moving money.
    class Meta:
        model = PayoutAccount
        fields = ["bank_name", "account_name", "account_last4"]