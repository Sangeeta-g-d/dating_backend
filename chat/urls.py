from django.urls import path

from .views import *


urlpatterns = [
    path('chat-history/<int:user_id>/', ChatRoomHistoryAPIView.as_view(), name='chat-history'),
    path('inbox/',InboxUserListAPIView.as_view(),name="inbox"),
    path('send-media/<int:room_id>/',MediaMessageUploadAPIView.as_view(),name="send-media"),
    path('delete-messages/<int:room_id>/',DeleteMessagesAPIView.as_view,name="delete-messages"),
    path('bg-img/',ChatBackgroundListAPIView.as_view(),name="bg-img"),
    path("set-bg/",SetChatBackgroundAPIView.as_view(),name="set-bg"),

    # audio call
    path("audio/start/", StartAudioCallAPIView.as_view()),
    path("audio/accept/", AcceptAudioCallAPIView.as_view()),
    path("audio/reject/", RejectAudioCallAPIView.as_view()),
    path("audio/end/", EndAudioCallAPIView.as_view()),
    path("audio/join/", JoinAudioCallAPIView.as_view()),  # For reconnection
    path("audio/token/refresh/", CallTokenRefreshAPIView.as_view()),  # Token refresh


    # video call
    path("video/start/", StartVideoCallAPIView.as_view()),
    path("video/accept/", AcceptVideoCallAPIView.as_view()),
    path("video/reject/", RejectVideoCallAPIView.as_view()),
    path("video/end/", EndVideoCallAPIView.as_view()),
    path("video/join/", JoinVideoCallAPIView.as_view()),
]