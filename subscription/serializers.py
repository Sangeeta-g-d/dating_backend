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

class SubscriptionInitSerializer(serializers.Serializer):
    """
    Serializer used to initiate a subscription purchase.
    The server will create a Razorpay order for the selected plan.
    """

    plan_id = serializers.IntegerField()

    def validate(self, attrs):
        plan_id = attrs.get("plan_id")
        try:
            plan = SubscriptionPlan.objects.get(id=plan_id)
        except SubscriptionPlan.DoesNotExist:
            raise serializers.ValidationError({"plan_id": "Invalid or inactive plan selected"})

        if plan.plan_type == "free":
            raise serializers.ValidationError({"plan_id": "Cannot purchase a free plan"})

        attrs["plan"] = plan
        return attrs


class PaymentConfirmSerializer(serializers.Serializer):
    """
    Serializer for confirming a payment after Razorpay Checkout.
    """

    razorpay_order_id = serializers.CharField()
    razorpay_payment_id = serializers.CharField()
    razorpay_signature = serializers.CharField()