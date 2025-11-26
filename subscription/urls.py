from django.urls import path
from .views import *

urlpatterns = [
    path('plans/', SubscriptionPlanListAPIView.as_view(), name='subscription-plans'),
    path('purchase/', PurchaseSubscriptionAPIView.as_view(), name='purchase-subscription'),
    path('activate_plan/',ActiveSubscriptionAPIView.as_view(),name="activate-subscription-plan"),
]