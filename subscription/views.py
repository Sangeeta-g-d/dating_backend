from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from admin_part.models import SubscriptionPlan,Transaction,UserSubscription
from .serializers import *
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from datetime import timedelta
from dating_backend.timezone_utils import format_to_ist

class SubscriptionPlanListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        plans = SubscriptionPlan.objects.all()
        serializer = SubscriptionPlanSerializer(plans, many=True, context={"request": request})

        return Response({
            "status": "200",
            "message": "Subscription plans fetched successfully",
            "Response": serializer.data
        }, status=status.HTTP_200_OK)


class PurchaseSubscriptionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SubscriptionPurchaseSerializer(data=request.data)

        # ❌ Serializer Invalid
        if not serializer.is_valid():
            return Response({
                "status": "400",
                "message": "Subscription purchase failed",
                "Response": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        plan = serializer.validated_data['plan']
        payment_id = serializer.validated_data['payment_id']
        amount = serializer.validated_data['amount']

        # 🔥 Prevent multiple active plans
        active_sub = UserSubscription.objects.filter(user=user, is_active=True, end_date__gte=timezone.now()).first()
        if active_sub:
            return Response({
                "status": "400",
                "message": "You already have an active subscription",
                "Response": {
                    "current_plan": active_sub.plan.name,
                    "valid_till": format_to_ist(active_sub.end_date)
                }
            }, status=status.HTTP_400_BAD_REQUEST)

        # 💳 Store Transaction
        transaction = Transaction.objects.create(
            user=user, plan=plan, payment_id=payment_id,
            amount=amount, status="completed"
        )

        # Activate Subscription
        subscription, created = UserSubscription.objects.get_or_create(user=user)
        subscription.plan = plan
        subscription.start_date = timezone.now()
        subscription.end_date = timezone.now() + timedelta(days=plan.duration_days)
        subscription.is_active = True
        subscription.save()

        # Final API Response
        return Response({
            "status": "200",
            "message": "Subscription activated successfully",
            "Response": {
                "plan": plan.name,
                "price": str(plan.price),
                "duration_days": plan.duration_days,
                "valid_till": format_to_ist(subscription.end_date),  # ⏳ IST format
                "transaction_id": transaction.id,
                "payment_id": payment_id
            }
        }, status=status.HTTP_200_OK)
    

class ActiveSubscriptionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Fetch active subscription
        subscription = UserSubscription.objects.filter(
            user=user, is_active=True, end_date__gte=timezone.now()
        ).first()

        # ❌ No active plan
        if not subscription:
            return Response({
                "status": "404",
                "message": "No active subscription found",
                "Response": None
            }, status=status.HTTP_404_NOT_FOUND)

        # Fetch latest successful payment for this plan
        last_txn = Transaction.objects.filter(
            user=user, plan=subscription.plan, status="completed"
        ).order_by('-id').first()

        return Response({
            "status": "200",
            "message": "Active subscription fetched successfully",
            "Response": {
                "plan_name": subscription.plan.name,
                "plan_type": subscription.plan.plan_type,
                "price": str(subscription.plan.price),
                "duration_days": subscription.plan.duration_days,
                "remaining_days": subscription.remaining_days(),
                "valid_till": format_to_ist(subscription.end_date),
                "transaction_id": last_txn.id if last_txn else None,
                "payment_id": last_txn.payment_id if last_txn else None,
                "purchased_on": format_to_ist(last_txn.created_at) if last_txn else None
            }
        }, status=status.HTTP_200_OK)
