from django.urls import path

from .views import *


urlpatterns = [
    path('chat-history/<int:user_id>/', ChatRoomHistoryAPIView.as_view(), name='chat-history'),
    path('inbox/',InboxUserListAPIView.as_view(),name="inbox")
]