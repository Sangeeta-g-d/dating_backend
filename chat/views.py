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
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

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

import logging
from .models import ChatRoom, Message

logger = logging.getLogger(__name__)



class DeleteMessagesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, room_id):
        user = request.user
        message_ids = request.data.get("message_ids", [])
        
        # Log the request for debugging
        logger.info(f"Delete request from user {user.id} ({user.email}) for room {room_id}")
        logger.info(f"Message IDs to delete: {message_ids}")

        # Validate message_ids parameter
        if not isinstance(message_ids, list) or len(message_ids) == 0:
            return Response({
                "status": 400,
                "message": "message_ids must be a non-empty list",
                "Response": {}
            }, status=400)

        # Validate that all message_ids are integers
        try:
            message_ids = [int(msg_id) for msg_id in message_ids]
        except (ValueError, TypeError):
            return Response({
                "status": 400,
                "message": "All message_ids must be valid integers",
                "Response": {}
            }, status=400)

        try:
            # Verify user is a participant in the chat room
            room = ChatRoom.objects.get(
                Q(user_a=user) | Q(user_b=user),
                id=room_id
            )
            logger.info(f"User {user.id} authorized for room {room_id}")
            
        except ChatRoom.DoesNotExist:
            logger.warning(f"User {user.id} attempted to access room {room_id} without authorization")
            return Response({
                "status": 403,
                "message": "You are not a participant in this chat room or room does not exist",
                "Response": {}
            }, status=403)

        # Fetch only the messages that belong to the user in this specific room
        messages = Message.objects.filter(
            id__in=message_ids,
            room=room,
            sender=user  # Users can only delete their own messages
        )

        if not messages.exists():
            logger.warning(f"No messages found for deletion by user {user.id} in room {room_id}")
            return Response({
                "status": 404,
                "message": "No messages found for deletion. You can only delete your own messages.",
                "Response": {}
            }, status=404)

        # Get the message IDs before deletion for the response
        found_message_ids = list(messages.values_list('id', flat=True))
        
        # Check if any requested messages weren't found (not owned by user or don't exist)
        not_found_ids = set(message_ids) - set(found_message_ids)
        if not_found_ids:
            logger.info(f"User {user.id} attempted to delete non-owned messages: {not_found_ids}")

        # Mark messages as deleted
        update_count = messages.update(is_deleted=True, updated_at=timezone.now())
        logger.info(f"Marked {update_count} messages as deleted by user {user.id}")

        # Prepare WebSocket payload
        deleted_payload = {
            "type": "delete_message",
            "deleted_message_ids": found_message_ids,
            "deleted_by": user.id,
            "room_id": room_id,
            "timestamp": timezone.now().isoformat()
        }

        # Broadcast deletion via WebSocket to all room participants
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"chat_{room_id}",
                {
                    "type": "chat.delete",
                    "data": deleted_payload
                }
            )
            logger.info(f"Broadcasted deletion of {len(found_message_ids)} messages to room {room_id}")
        except Exception as e:
            logger.error(f"Failed to broadcast deletion via WebSocket: {str(e)}")
            # Don't fail the request if WebSocket fails, just log it

        # Prepare response
        response_data = {
            "status": 200,
            "message": f"Successfully deleted {len(found_message_ids)} message(s)",
            "Response": {
                "deleted_message_ids": found_message_ids,
                "room_id": room_id,
                "not_found_or_unauthorized": list(not_found_ids) if not_found_ids else []
            }
        }

        # Add warning if some messages couldn't be deleted
        if not_found_ids:
            response_data["message"] += f". {len(not_found_ids)} message(s) could not be deleted (not found or not owned by you)"

        return Response(response_data, status=200)