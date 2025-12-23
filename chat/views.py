from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import ChatRoom, Message, MessageReceipt
from .serializers import ChatRoomSerializer, MessageSerializer,ChatBackgroundSerializer
from .pagination import StandardResultsPagination
from auth_api.models import CustomUser
from dating_backend.timezone_utils import format_to_ist
from django.db.models import Q
from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from admin_part.models import ChatBackground
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

        chatrooms = ChatRoom.objects.filter(
            (Q(user_a=user) | Q(user_b=user)),
            messages__isnull=False
        ).distinct().order_by("-last_message_at")

        inbox_list = []

        for room in chatrooms:
            other_user = room.user_b if room.user_a == user else room.user_a
            last_msg = room.messages.order_by("-created_at").first()

            if not last_msg:
                continue

            last_message_text = "Media" if last_msg.media else last_msg.content or ""
            last_message_time = format_to_ist(last_msg.created_at)

            unseen_count = MessageReceipt.objects.filter(
                message__room=room,
                user=user,
                seen_at__isnull=True
            ).count()

            profile_url = (
                request.build_absolute_uri(other_user.profile_photo.url)
                if other_user.profile_photo else None
            )

            # ✅ Chat background info
            background_id = user.chat_background.id if user.chat_background else None
            background_image = (
                request.build_absolute_uri(user.chat_background.image.url)
                if user.chat_background and user.chat_background.image
                else None
            )

            inbox_list.append({
                "room_id": room.id,
                "user": {
                    "id": other_user.id,
                    "full_name": other_user.full_name,
                    "profile_photo": profile_url,
                },
                "last_message": last_message_text,
                "last_message_time": last_message_time,
                "unseen_count": unseen_count,

                # ✅ Added fields
                "chat_background": {
                    "background_id": background_id,
                    "image": background_image
                }
            })

        return Response({
            "status": "200",
            "message": "Inbox users fetched successfully",
            "Response": inbox_list,
        }, status=status.HTTP_200_OK)





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
                "type": "media_message",
                "message": message_data,
            }
        )

        # Final API Response
        return Response({
            "status": 200,
            "message": "Media message sent successfully",
            "Response": message_data,
        }, status=200)


@method_decorator(csrf_exempt, name='dispatch')
class DeleteMessagesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        message_ids = request.data.get("message_ids", [])

        # Convert single ID → list automatically
        if isinstance(message_ids, int):
            message_ids = [message_ids]

        if not isinstance(message_ids, list) or not message_ids:
            return Response({"error": "message_ids must be a list"}, status=400)

        # Fetch only user's own messages
        messages = Message.objects.filter(id__in=message_ids, sender=request.user)

        if not messages.exists():
            return Response({"error": "No deletable messages found"}, status=404)

        room_id = messages.first().room_id  # All messages belong to same room in 1v1 chat

        # Delete media + receipts
        for msg in messages:
            MessageReceipt.objects.filter(message=msg).delete()
            if msg.media:
                msg.media.delete(save=False)

        # Finally delete messages
        messages.delete()

        # WebSocket broadcast
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"chat_{room_id}",
            {
                "type": "chat_delete",
                "data": {
                    "event": "messages_deleted",
                    "message_ids": message_ids,
                }
            }
        )

        return Response({"message": "Messages deleted"}, status=200)


class ChatBackgroundListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        backgrounds = ChatBackground.objects.all()

        serializer = ChatBackgroundSerializer(
            backgrounds,
            many=True,
            context={'request': request}
        )

        return Response({
            "status": "200",
            "message": "Chat backgrounds fetched successfully",
            "Response": serializer.data
        })

class SetChatBackgroundAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Set chat background for logged-in user
        """
        user = request.user
        background_id = request.data.get("background_id")

        if not background_id:
            return Response({
                "status": "400",
                "message": "background_id is required",
                "Response": []
            }, status=status.HTTP_400_BAD_REQUEST)

        background = get_object_or_404(ChatBackground, id=background_id)

        user.chat_background = background
        user.save(update_fields=["chat_background"])

        return Response({
            "status": "200",
            "message": "Chat background updated successfully",
            "Response": {
                "background_id": background.id,
                "name": background.name,
                "image": request.build_absolute_uri(background.image.url)
            }
        }, status=status.HTTP_200_OK)


from agora_token_builder import RtcTokenBuilder
from django.conf import settings
import time
import uuid
from .models import AudioCall
from notifications.utils import create_notification
import uuid
import time
from datetime import datetime
from agora_token_builder import RtcTokenBuilder
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.conf import settings
from .models import CustomUser, AudioCall
from notifications.utils import create_notification

class StartAudioCallAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        receiver_id = request.data.get("receiver_id")

        if not receiver_id:
            return Response({"error": "receiver_id required"}, status=400)

        try:
            receiver = CustomUser.objects.get(id=receiver_id)
        except CustomUser.DoesNotExist:
            return Response({"error": "Receiver not found"}, status=404)

        channel_name = f"audio_call_{uuid.uuid4().hex}"

        # Create call
        call = AudioCall.objects.create(
            caller=request.user,
            receiver=receiver,
            channel_name=channel_name,
            status="ringing"
        )

        # Schedule auto-expire task
        expire_audio_call.apply_async(
            args=[call.id],
            countdown=settings.CALL_RING_TIMEOUT
        )

        # Generate token for caller
        caller_token = self._generate_token(channel_name, request.user.id)

        # Notify receiver
        create_notification(
            receiver=receiver,
            sender=request.user,
            notif_type="incoming_call",
            message="Incoming audio call",
            extra_data={
                "call_type": "audio",
                "call_id": str(call.id),
                "channel_name": channel_name,
                "caller_id": str(request.user.id),
                "caller_name": request.user.full_name,
                "app_id": settings.AGORA_APP_ID
            }
        )

        return Response({
            "status": "ringing",
            "call_id": call.id,
            "channel_name": channel_name,
            "app_id": settings.AGORA_APP_ID,
            "token": caller_token,
            "uid": request.user.id
        })

    def _generate_token(self, channel_name, uid, role=1):
        expire_time = 3600
        current_time = int(time.time())
        privilege_expired_ts = current_time + expire_time

        return RtcTokenBuilder.buildTokenWithUid(
            settings.AGORA_APP_ID,
            settings.AGORA_APP_CERTIFICATE,
            channel_name,
            uid,
            role,
            privilege_expired_ts
        )


class AcceptAudioCallAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        call_id = request.data.get("call_id")

        if not call_id:
            return Response({"error": "call_id required"}, status=400)

        try:
            call = AudioCall.objects.get(
                id=call_id,
                receiver=request.user
            )
        except AudioCall.DoesNotExist:
            return Response(
                {"error": "Call not found or unauthorized"},
                status=404
            )

        # ❌ Call already handled
        if call.status != "ringing":
            return Response(
                {"error": f"Call already {call.status}"},
                status=400
            )

        print("\n✅ [CALL ACCEPTED]")
        print("User:", request.user.id)
        print("Channel:", call.channel_name)

        # Update call state
        call.status = "accepted"
        call.accepted_at = timezone.now()
        call.save()

        # Generate Agora token for receiver
        token = self._generate_token(
            call.channel_name,
            request.user.id
        )

        # Notify caller
        create_notification(
            receiver=call.caller,
            sender=request.user,
            notif_type="call_accepted",
            message="Call accepted",
            extra_data={
                "call_id": str(call.id),
                "channel_name": call.channel_name
            }
        )

        return Response({
            "app_id": settings.AGORA_APP_ID,
            "token": token,
            "channel_name": call.channel_name,
            "uid": request.user.id,
            "call_id": call.id,
            "caller_id": call.caller.id,
            "caller_name": call.caller.full_name
        })

    def _generate_token(self, channel_name, uid, role=1):
        expire_time = 3600
        privilege_expired_ts = int(time.time()) + expire_time

        return RtcTokenBuilder.buildTokenWithUid(
            settings.AGORA_APP_ID,
            settings.AGORA_APP_CERTIFICATE,
            channel_name,
            uid,
            role,
            privilege_expired_ts
        )


class JoinAudioCallAPIView(APIView):
    """API for user to rejoin an ongoing call"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        call_id = request.data.get("call_id")

        if not call_id:
            return Response({"error": "call_id required"}, status=400)

        try:
            call = AudioCall.objects.get(id=call_id)
        except AudioCall.DoesNotExist:
            return Response({"error": "Call not found"}, status=404)

        # Authorization
        if request.user not in [call.caller, call.receiver]:
            return Response(
                {"error": "Unauthorized to join this call"},
                status=403
            )

        # Only accepted calls can be joined
        if call.status != "accepted":
            return Response(
                {"error": f"Call is {call.status}, cannot join"},
                status=400
            )

        token = self._generate_token(
            call.channel_name,
            request.user.id
        )

        print(
            f"\n🔗 [USER REJOINED CALL] User: {request.user.id}, Call: {call.id}"
        )

        other_user = (
            call.caller if request.user == call.receiver else call.receiver
        )

        return Response({
            "app_id": settings.AGORA_APP_ID,
            "token": token,
            "channel_name": call.channel_name,
            "uid": request.user.id,
            "call_id": call.id,
            "other_user_id": other_user.id,
            "other_user_name": other_user.full_name
        })

    def _generate_token(self, channel_name, uid, role=1):
        expire_time = 3600
        privilege_expired_ts = int(time.time()) + expire_time

        return RtcTokenBuilder.buildTokenWithUid(
            settings.AGORA_APP_ID,
            settings.AGORA_APP_CERTIFICATE,
            channel_name,
            uid,
            role,
            privilege_expired_ts
        )


class RejectAudioCallAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        call_id = request.data.get("call_id")

        if not call_id:
            return Response({"error": "call_id required"}, status=400)

        try:
            call = AudioCall.objects.get(
                id=call_id,
                receiver=request.user
            )
        except AudioCall.DoesNotExist:
            return Response(
                {"error": "Call not found or unauthorized"},
                status=404
            )

        # ❌ Call already handled
        if call.status != "ringing":
            return Response(
                {"error": f"Call already {call.status}"},
                status=400
            )

        print("\n❌ [CALL REJECTED]")
        print("Call ID:", call.id)

        # Update call state
        call.status = "rejected"
        call.ended_at = timezone.now()
        call.save()

        # Notify caller
        create_notification(
            receiver=call.caller,
            sender=request.user,
            notif_type="missed_call",
            message="Missed audio call",
            extra_data={
                "call_id": str(call.id),
                "call_type": "audio"
            }
        )

        return Response({
            "status": "rejected",
            "call_id": call.id
        })



class EndAudioCallAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        call_id = request.data.get("call_id")

        if not call_id:
            return Response({"error": "call_id required"}, status=400)

        try:
            call = AudioCall.objects.get(id=call_id)
        except AudioCall.DoesNotExist:
            return Response({"error": "Call not found"}, status=404)

        # Authorization
        if request.user not in [call.caller, call.receiver]:
            return Response(
                {"error": "Unauthorized to end this call"},
                status=403
            )

        # Only accepted calls can be ended
        if call.status != "accepted":
            return Response(
                {"error": f"Cannot end call in {call.status} state"},
                status=400
            )

        print("\n📴 [CALL ENDED]")
        print("Call ID:", call.id)
        print("Ended by:", request.user.id)

        call.status = "ended"
        call.ended_at = timezone.now()
        call.save()

        other_user = (
            call.receiver if request.user == call.caller else call.caller
        )

        create_notification(
            receiver=other_user,
            sender=request.user,
            notif_type="call_ended",
            message="Call ended",
            extra_data={
                "call_id": str(call.id),
                "ended_by_id": str(request.user.id),
                "ended_by_name": request.user.full_name
            }
        )

        return Response({
            "status": "ended",
            "call_id": call.id,
            "ended_by": request.user.id
        })

class CallTokenRefreshAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        call_id = request.data.get("call_id")

        if not call_id:
            return Response({"error": "call_id required"}, status=400)

        try:
            call = AudioCall.objects.get(id=call_id)
        except AudioCall.DoesNotExist:
            return Response({"error": "Call not found"}, status=404)

        if request.user not in [call.caller, call.receiver]:
            return Response(
                {"error": "Unauthorized"},
                status=403
            )

        if call.status in ["ended", "missed", "rejected"]:
            return Response(
                {"error": f"Call already {call.status}"},
                status=400
            )

        token = self._generate_token(
            call.channel_name,
            request.user.id
        )

        return Response({
            "token": token,
            "app_id": settings.AGORA_APP_ID,
            "uid": request.user.id,
            "channel_name": call.channel_name,
            "expires_in": 3600
        })

    def _generate_token(self, channel_name, uid, role=1):
        expire_time = 3600
        privilege_expired_ts = int(time.time()) + expire_time

        return RtcTokenBuilder.buildTokenWithUid(
            settings.AGORA_APP_ID,
            settings.AGORA_APP_CERTIFICATE,
            channel_name,
            uid,
            role,
            privilege_expired_ts
        )
