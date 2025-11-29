# subscription/serializers.py

from rest_framework import serializers
from admin_part.models import SubscriptionPlan
class SubscriptionPlanSerializer(serializers.ModelSerializer):
    is_subscribed = serializers.SerializerMethodField()
    expiry_days_left = serializers.SerializerMethodField()

    class Meta:
        model = SubscriptionPlan
        fields = "__all__"  # + the 2 new fields automatically included

    def get_is_subscribed(self, obj):
        """
        Check if logged-in user is currently subscribed to this plan.
        """
        user = self.context["request"].user
        subscription = getattr(user, "subscription", None)

        return bool(subscription and subscription.plan == obj and subscription.is_active)

    def get_expiry_days_left(self, obj):
        """
        Return remaining days only if user is subscribed to this plan.
        Else return None.
        """
        user = self.context["request"].user
        subscription = getattr(user, "subscription", None)

        if subscription and subscription.plan == obj and subscription.is_active:
            return subscription.remaining_days()   # uses model function
        return None

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