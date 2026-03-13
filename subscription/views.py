import json
import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import transaction

from admin_part.models import SubscriptionPlan, Transaction, UserSubscription
from dating_backend.timezone_utils import format_to_ist
from .razorpay_client import (
    create_order,
    fetch_payment,
    verify_payment_signature,
    verify_webhook_signature,
)
from .serializers import (
    PaymentConfirmSerializer,
    SubscriptionInitSerializer,
    SubscriptionPlanSerializer,
)

logger = logging.getLogger(__name__)


class SubscriptionPlanListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        plans = SubscriptionPlan.objects.all()
        serializer = SubscriptionPlanSerializer(plans, many=True, context={"request": request})

        return Response(
            {
                "status": "200",
                "message": "Subscription plans fetched successfully",
                "Response": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class SubscriptionPurchaseInitAPIView(APIView):
    """
    Step 1: Initiate a subscription purchase.
    Creates a Razorpay order and a pending Transaction.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SubscriptionInitSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "status": "400",
                    "message": "Subscription purchase init failed",
                    "Response": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        plan = serializer.validated_data["plan"]

        active_sub = UserSubscription.objects.filter(
            user=user, is_active=True, end_date__gte=timezone.now()
        ).first()
        if active_sub:
            return Response(
                {
                    "status": "400",
                    "message": "You already have an active subscription",
                    "Response": {
                        "current_plan": active_sub.plan.name,
                        "valid_till": format_to_ist(active_sub.end_date),
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        amount_rupees = plan.price
        amount_paise = int(amount_rupees * 100)

        try:
            order = create_order(
                amount_paise=amount_paise,
                currency="INR",
                notes={"user_id": user.id, "plan_id": plan.id, "payment_type": "subscription"},
            )
        except Exception:
            logger.exception("Failed to create Razorpay order")
            return Response(
                {
                    "status": "500",
                    "message": "Failed to initiate payment",
                    "Response": {"detail": "Unable to create Razorpay order"},
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        razorpay_order_id = order.get("id")

        transaction = Transaction.objects.create(
            user=user,
            plan=plan,
            payment_type="subscription",
            amount=amount_rupees,
            currency="INR",
            razorpay_order_id=razorpay_order_id,
            status="pending",
            gateway_status=order.get("status"),
        )

        return Response(
            {
                "status": "200",
                "message": "Subscription purchase initiated",
                "Response": {
                    "order_id": razorpay_order_id,
                    "amount": amount_rupees,
                    "currency": "INR",
                    "key_id": settings.RAZORPAY_KEY_ID,
                    "transaction_id": transaction.id,
                    "plan": {
                        "id": plan.id,
                        "name": plan.name,
                        "price": str(plan.price),
                        "duration_days": plan.duration_days,
                    },
                },
            },
            status=status.HTTP_200_OK,
        )


class PaymentConfirmAPIView(APIView):
    """
    Step 2: Confirm payment after Razorpay Checkout.
    Verifies signature and activates the subscription if payment is captured.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PaymentConfirmSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "status": "400",
                    "message": "Payment confirmation failed",
                    "Response": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        razorpay_order_id = serializer.validated_data["razorpay_order_id"]
        razorpay_payment_id = serializer.validated_data["razorpay_payment_id"]
        razorpay_signature = serializer.validated_data["razorpay_signature"]

        try:
            with transaction.atomic():
                transaction_obj  = Transaction.objects.select_for_update().get(
                    user=user, razorpay_order_id=razorpay_order_id
                )
        except transaction_obj.DoesNotExist:
            return Response(
                {
                    "status": "404",
                    "message": "Transaction not found for this order",
                    "Response": None,
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if transaction_obj.status == "completed":
            return Response(
                {
                    "status": "200",
                    "message": "Payment already confirmed",
                    "Response": {
                        "transaction_id": transaction_obj.id,
                        "plan": transaction_obj.plan.name if transaction_obj.plan else None,
                    },
                },
                status=status.HTTP_200_OK,
            )

        if not verify_payment_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature):
            transaction_obj.status = "failed"
            transaction_obj.gateway_status = "signature_verification_failed"
            transaction_obj.save(update_fields=["status", "gateway_status"])
            return Response(
                {
                    "status": "400",
                    "message": "Invalid payment signature",
                    "Response": None,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            payment = fetch_payment(razorpay_payment_id)
        except Exception:
            logger.exception("Failed to fetch Razorpay payment")
            return Response(
                {
                    "status": "502",
                    "message": "Unable to verify payment with gateway",
                    "Response": None,
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        payment_status = payment.get("status")
        amount_received = payment.get("amount")
        currency = payment.get("currency")

        expected_amount_paise = int(transaction_obj.amount * 100)

        if (
            payment_status != "captured"
            or amount_received != expected_amount_paise
            or currency != transaction_obj.currency
        ):
            transaction_obj.status = "failed"
            transaction_obj.gateway_status = payment_status
            transaction_obj.razorpay_payment_id = razorpay_payment_id
            transaction_obj.razorpay_signature = razorpay_signature
            transaction_obj.save(
                update_fields=[
                    "status",
                    "gateway_status",
                    "razorpay_payment_id",
                    "razorpay_signature",
                ]
            )
            logger.warning(
                "Payment verification failed or mismatched amount",
                extra={
                    "transaction_id": transaction_obj.id,
                    "payment_status": payment_status,
                    "amount_received": amount_received,
                    "expected_amount": expected_amount_paise,
                },
            )
            return Response(
                {
                    "status": "400",
                    "message": "Payment not successful or amount mismatch",
                    "Response": None,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        transaction_obj.status = "completed"
        transaction_obj.gateway_status = payment_status
        transaction_obj.razorpay_payment_id = razorpay_payment_id
        transaction_obj.razorpay_signature = razorpay_signature
        transaction_obj.save(
            update_fields=[
                "status",
                "gateway_status",
                "razorpay_payment_id",
                "razorpay_signature",
            ]
        )

        plan = transaction_obj.plan
        subscription, _ = UserSubscription.objects.get_or_create(user=user)
        subscription.plan = plan
        subscription.start_date = timezone.now()
        subscription.end_date = timezone.now() + timedelta(days=plan.duration_days)
        subscription.is_active = True
        subscription.save()

        return Response(
            {
                "status": "200",
                "message": "Subscription activated successfully",
                "Response": {
                    "plan": plan.name if plan else None,
                    "price": str(plan.price) if plan else None,
                    "duration_days": plan.duration_days if plan else None,
                    "valid_till": format_to_ist(subscription.end_date),
                    "transaction_id": transaction.id,
                    "payment_id": razorpay_payment_id,
                },
            },
            status=status.HTTP_200_OK,
        )


class RazorpayWebhookView(APIView):
    """
    Webhook endpoint for Razorpay events.
    Used as a secondary source of truth / reconciliation.
    """

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        signature = request.headers.get("X-Razorpay-Signature", "")
        payload = request.body

        if not verify_webhook_signature(payload, signature):
            return Response(
                {
                    "status": "400",
                    "message": "Invalid webhook signature",
                    "Response": None,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            data = json.loads(payload.decode("utf-8"))
        except json.JSONDecodeError:
            return Response(
                {
                    "status": "400",
                    "message": "Invalid webhook payload",
                    "Response": None,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        event = data.get("event")
        payload_entity = data.get("payload", {})

        if event in ("payment.captured", "payment.failed"):
            payment_entity = payload_entity.get("payment", {}).get("entity", {})
            razorpay_payment_id = payment_entity.get("id")
            razorpay_order_id = payment_entity.get("order_id")
            status_value = payment_entity.get("status")

            try:
                transaction = Transaction.objects.get(razorpay_order_id=razorpay_order_id)
            except Transaction.DoesNotExist:
                logger.warning(
                    "Webhook for unknown order",
                    extra={"razorpay_order_id": razorpay_order_id, "event": event},
                )
                return Response(
                    {
                        "status": "200",
                        "message": "Webhook received for unknown order",
                        "Response": None,
                    },
                    status=status.HTTP_200_OK,
                )

            if transaction.status == "completed":
                return Response(
                    {
                        "status": "200",
                        "message": "Transaction already completed",
                        "Response": {"transaction_id": transaction.id},
                    },
                    status=status.HTTP_200_OK,
                )

            if status_value == "captured":
                transaction.status = "completed"
            elif status_value == "failed":
                transaction.status = "failed"

            transaction.gateway_status = status_value
            if razorpay_payment_id:
                transaction.razorpay_payment_id = transaction.razorpay_payment_id or razorpay_payment_id
            transaction.save(update_fields=["status", "gateway_status", "razorpay_payment_id"])

        return Response(
            {
                "status": "200",
                "message": "Webhook processed",
                "Response": None,
            },
            status=status.HTTP_200_OK,
        )


class ActiveSubscriptionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        subscription = UserSubscription.objects.filter(
            user=user, is_active=True, end_date__gte=timezone.now()
        ).first()

        if not subscription:
            return Response(
                {
                    "status": "404",
                    "message": "No active subscription found",
                    "Response": None,
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        last_txn = (
            Transaction.objects.filter(user=user, plan=subscription.plan, status="completed")
            .order_by("-id")
            .first()
        )

        return Response(
            {
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
                    "payment_id": last_txn.razorpay_payment_id if last_txn else None,
                    "purchased_on": format_to_ist(last_txn.created_at) if last_txn else None,
                },
            },
            status=status.HTTP_200_OK,
        )