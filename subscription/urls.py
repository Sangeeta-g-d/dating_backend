from django.urls import path

from .views import (
    ActiveSubscriptionAPIView,
    PaymentConfirmAPIView,
    RazorpayWebhookView,
    SubscriptionPlanListAPIView,
    SubscriptionPurchaseInitAPIView,
)

urlpatterns = [
    path("plans/", SubscriptionPlanListAPIView.as_view(), name="subscription-plans"),
    path(
        "purchase/",
        SubscriptionPurchaseInitAPIView.as_view(),
        name="purchase-subscription",
    ),
    path(
        "payment/confirm/",
        PaymentConfirmAPIView.as_view(),
        name="payment-confirm",
    ),
    path(
        "webhook/razorpay/",
        RazorpayWebhookView.as_view(),
        name="razorpay-webhook",
    ),
    path(
        "activate_plan/",
        ActiveSubscriptionAPIView.as_view(),
        name="activate-subscription-plan",
    ),
]