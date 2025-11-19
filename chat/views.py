from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import ChatRoom, Message, CustomUser
from .serializers import ChatRoomSerializer, MessageSerializer
from .pagination import StandardResultsPagination


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
        try:
            current_user = request.user
            other_user = get_object_or_404(CustomUser, id=user_id)

            if current_user.id == other_user.id:
                return Response({
                    "status": "400",
                    "message": "Cannot create chat room with yourself"
                }, status=status.HTTP_400_BAD_REQUEST)

            room, created = self.get_room(current_user, other_user)

            # Fetch messages oldest → newest
            messages = Message.objects.filter(room=room).order_by("-created_at")

            paginator = StandardResultsPagination()
            paginated_messages = paginator.paginate_queryset(messages, request)

            # Only serialize messages
            msg_serializer = MessageSerializer(
                paginated_messages,
                many=True,
                context={"request": request}
            )

            # ⛔ DO NOT USE ChatRoomSerializer HERE
            # Instead, return only room ID
            room_data = {
                "id": room.id
            }

            response_data = {
                "status": "200",
                "message": "Chat fetched successfully" if not created else "New chat room created",
                "Response": {
                    "room": room_data,
                    "messages": msg_serializer.data,
                }
            }

            return paginator.get_paginated_response(response_data)

        except Exception as e:
            return Response({
                "status": "500",
                "message": f"Error fetching chat history: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
