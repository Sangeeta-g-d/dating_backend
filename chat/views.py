from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from rest_framework.permissions import IsAuthenticated
from .models import ChatRoom, Message, MessageReceipt
from .serializers import MessageSerializer, ChatRoomSerializer
from auth_api.models import CustomUser
from dating_backend.timezone_utils import format_to_ist

from rest_framework.pagination import PageNumberPagination

class StandardResultsPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


# fetch chat history
class ChatRoomHistoryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_room(self, user1, user2):
        user_a, user_b = sorted([user1, user2], key=lambda x: x.id)
        room, created = ChatRoom.objects.get_or_create(
            user_a=user_a,
            user_b=user_b
        )
        return room, created

    def get(self, request, user_id):
        current_user = request.user
        other_user = get_object_or_404(CustomUser, id=user_id)

        room, created = self.get_room(current_user, other_user)

        messages = Message.objects.filter(room=room).order_by("-created_at")

        paginator = StandardResultsPagination()
        paginated_messages = paginator.paginate_queryset(messages, request)

        room_serializer = ChatRoomSerializer(room, context={"request": request})
        msg_serializer = MessageSerializer(paginated_messages, many=True, context={"request": request})

        response_data = {
            "status": "200",
            "message": "Chat fetched successfully" if not created else "New chat room created",
            "Response": {
                "room": room_serializer.data,
                "messages": msg_serializer.data,
            }
        }

        return paginator.get_paginated_response(response_data)
