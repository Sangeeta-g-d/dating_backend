from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import ChatRoom, Message, MessageReceipt
from .serializers import ChatRoomSerializer, MessageSerializer
from .pagination import StandardResultsPagination
from auth_api.models import CustomUser
from dating_backend.timezone_utils import format_to_ist
from django.db.models import Q
from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

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



class InboxUserListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Fetch chatrooms where current user is a participant
        chatrooms = ChatRoom.objects.filter(
            Q(user_a=user) | Q(user_b=user)
        ).order_by("-last_message_at")

        inbox_list = []

        for room in chatrooms:
            # Determine the other participant
            other_user = room.user_b if room.user_a == user else room.user_a

            # Last message
            last_msg = room.messages.order_by("-created_at").first()

            if last_msg:
                if last_msg.media:
                    last_message_text = "Media"
                else:
                    last_message_text = last_msg.content or ""
                
                last_message_time = format_to_ist(last_msg.created_at)
            else:
                last_message_text = ""
                last_message_time = None

            # Full profile URL
            if other_user.profile_photo:
                profile_url = request.build_absolute_uri(other_user.profile_photo.url)
            else:
                profile_url = None

            inbox_list.append({
                "room_id": room.id,
                "user": {
                    "id": other_user.id,
                    "full_name": other_user.full_name,
                    "profile_photo": profile_url,
                },
                "last_message": last_message_text,
                "last_message_time": last_message_time,
            })

        # Response without pagination
        response_data = {
            "status": "200",
            "message": "Inbox users fetched successfully",
            "Response": inbox_list,
        }

        return Response(response_data, status=status.HTTP_200_OK)



class MediaMessageUploadAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, room_id):
        user = request.user

        media_file = request.FILES.get("media")
        if not media_file:
            return Response({
                "status": 400,
                "message": "Media file is required",
                "Response": {}
            }, status=400)

        # Validate Chat Room
        try:
            room = ChatRoom.objects.get(id=room_id)
        except ChatRoom.DoesNotExist:
            return Response({
                "status": 404,
                "message": "Chat room not found",
                "Response": {}
            }, status=404)

        # Detect media type
        content_type = media_file.content_type.lower()

        if content_type.startswith("image"):
            media_type = Message.MEDIA_IMAGE
        elif content_type.startswith("video"):
            media_type = Message.MEDIA_VIDEO
        else:
            return Response({
                "status": 400,
                "message": "Unsupported media type",
                "Response": {}
            }, status=400)

        # Save Message
        message = Message.objects.create(
            room=room,
            sender=user,
            media=media_file,
            media_type=media_type,
            created_at=timezone.now(),
        )

        # Create receipts for both participants
        for participant in room.participants():
            MessageReceipt.objects.create(
                message=message,
                user=participant
            )

        # Format message response
        message_data = {
            "id": message.id,
            "room_id": room.id,
            "sender": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name if hasattr(user, "full_name") else "",
                "profile_image": request.build_absolute_uri(user.profile_image.url) if getattr(user, "profile_image", None) else None
            },
            "media_url": request.build_absolute_uri(message.media.url),
            "media_type": message.media_type,
            "created_at": format_to_ist(message.created_at),
            "is_deleted": message.is_deleted,
        }

        # Broadcast via WebSocket
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"chat_{room_id}",
            {
                "type": "chat.message",
                "message": message_data,
            }
        )

        # Final API Response
        return Response({
            "status": 200,
            "message": "Media message sent successfully",
            "Response": message_data,
        }, status=200)



class DeleteMessagesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, room_id):
        user = request.user

        message_ids = request.data.get("message_ids", [])
        if not isinstance(message_ids, list) or len(message_ids) == 0:
            return Response({
                "status": 400,
                "message": "message_ids must be a non-empty list",
                "Response": {}
            }, status=400)

        # Validate Chat Room
        try:
            room = ChatRoom.objects.get(id=room_id)
        except ChatRoom.DoesNotExist:
            return Response({
                "status": 404,
                "message": "Chat room not found",
                "Response": {}
            }, status=404)

        # Fetch messages
        messages = Message.objects.filter(id__in=message_ids, room=room)

        if not messages.exists():
            return Response({
                "status": 404,
                "message": "No messages found for deletion",
                "Response": {}
            }, status=404)

        # Mark messages as deleted
        messages.update(is_deleted=True, updated_at=timezone.now())

        # Prepare response data
        deleted_payload = []
        for msg in messages:
            deleted_payload.append({
                "id": msg.id,
                "room_id": room_id,
                "is_deleted": True,
                "deleted_at": format_to_ist(timezone.now())
            })

        # Broadcast delete event to WebSocket
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"chat_{room_id}",
            {
                "type": "chat.delete",
                "data": deleted_payload
            }
        )

        # Final API Response
        return Response({
            "status": 200,
            "message": "Message(s) deleted successfully",
            "Response": deleted_payload,
        }, status=200)
