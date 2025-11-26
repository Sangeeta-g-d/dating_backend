# subscription/serializers.py

from rest_framework import serializers
from admin_part.models import SubscriptionPlan

class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = "__all__"    # or manually list fields to restrict output
