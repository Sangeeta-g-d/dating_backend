from django.urls import path

from .views import (
    GetOrCreateChatRoomView,
    MessageListView,
    SendMessageView,
    MarkMessagesSeenView,
)

urlpatterns = [
    path("rooms/", GetOrCreateChatRoomView.as_view(), name="chat-room"),
    path("rooms/<int:room_id>/messages/", MessageListView.as_view(), name="chat-messages"),
    path("rooms/<int:room_id>/messages/send/", SendMessageView.as_view(), name="chat-send"),
    path("rooms/<int:room_id>/seen/", MarkMessagesSeenView.as_view(), name="chat-seen"),
]