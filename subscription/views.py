from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from admin_part.models import SubscriptionPlan
from .serializers import SubscriptionPlanSerializer
from rest_framework.permissions import IsAuthenticated


class SubscriptionPlanListAPIView(APIView):
    """Return list of all available subscription plans"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        plans = SubscriptionPlan.objects.all()

        serializer = SubscriptionPlanSerializer(plans, many=True)

        return Response({
            "status": "200",
            "message": "Subscription plans fetched successfully",
            "Response": serializer.data
        }, status=status.HTTP_200_OK)

