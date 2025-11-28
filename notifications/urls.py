from django.urls import path
from .views import *

urlpatterns = [
    path('notifications/', NotificationListAPIView.as_view(), name='notifications-list'),
    path('mark-as-read/', MarkAsReadAPIView.as_view(), name='mark-multiple-notifications'),

]