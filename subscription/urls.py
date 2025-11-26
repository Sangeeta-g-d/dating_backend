from django.urls import path
from .views import *

urlpatterns = [
    path('plans/', SubscriptionPlanListAPIView.as_view(), name='subscription-plans'),
]