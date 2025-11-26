# subscription/serializers.py

from rest_framework import serializers
from admin_part.models import SubscriptionPlan

class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = "__all__"    # or manually list fields to restrict output


class SubscriptionPurchaseSerializer(serializers.Serializer):
    plan_id = serializers.IntegerField()
    payment_id = serializers.CharField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)

    def validate(self, attrs):
        try:
            plan = SubscriptionPlan.objects.get(id=attrs['plan_id'])
            attrs['plan'] = plan
        except SubscriptionPlan.DoesNotExist:
            raise serializers.ValidationError({"plan_id": "Invalid or inactive plan selected"})

        return attrs