from operator import call
from django.dispatch import receiver
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import NotFound
from .models import ChatRoom, Message, MessageReceipt
from .serializers import ChatRoomSerializer, MessageSerializer, ChatBackgroundSerializer, CallHistorySerializer, ChatHistorySerializer
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
from rest_framework.pagination import PageNumberPagination

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
                    "success": "400",
                    "message": "Cannot create chat room with yourself",
                    "Response": []
                }, status=status.HTTP_400_BAD_REQUEST)

            room, created = self.get_room(current_user, other_user)

            # Fetch messages oldest → newest
            all_messages = Message.objects.filter(room=room).order_by("-created_at")

            paginator = StandardResultsPagination()
            
            try:
                paginated_messages = paginator.paginate_queryset(all_messages, request)
            except NotFound:
                # If page doesn't exist, return empty list with pagination info
                page_num = request.query_params.get('page', 1)
                try:
                    page_num = int(page_num)
                except (ValueError, TypeError):
                    page_num = 1
                
                total_items = all_messages.count()
                page_size = paginator.page_size
                total_pages = (total_items + page_size - 1) // page_size
                
                return Response({
                    "success": "200",
                    "message": "Chat history fetched successfully",
                    "Response": [],
                    "pagination": {
                        "current_page": page_num,
                        "page_size": page_size,
                        "total_items": total_items,
                        "total_pages": total_pages,
                        "has_next_page": False,
                        "has_previous_page": page_num > 1
                    }
                }, status=status.HTTP_200_OK)

            # Use ChatHistorySerializer for the desired format
            msg_serializer = ChatHistorySerializer(
                paginated_messages,
                many=True,
                context={"request": request}
            )

            # Calculate pagination info
            page_num = request.query_params.get('page', 1)
            try:
                page_num = int(page_num)
            except (ValueError, TypeError):
                page_num = 1

            total_items = all_messages.count()
            page_size = paginator.page_size
            total_pages = (total_items + page_size - 1) // page_size  # Ceiling division
            has_next_page = page_num < total_pages
            has_previous_page = page_num > 1

            response_data = {
                "success": "200",
                "message": "Chat history fetched successfully" if not created else "New chat room created",
                "Response": msg_serializer.data,
                "pagination": {
                    "current_page": page_num,
                    "page_size": page_size,
                    "total_items": total_items,
                    "total_pages": total_pages,
                    "has_next_page": has_next_page,
                    "has_previous_page": has_previous_page
                }
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "success": "500",
                "message": f"Error fetching chat history: {str(e)}",
                "Response": []
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

            # Count only messages sent by the *other* user that are still unseen
            unseen_count = MessageReceipt.objects.filter(
                message__room=room,
                message__sender=other_user,
                user=user,
                seen_at__isnull=True,
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

        # Format message response in standardized format (matching new_message format)
        message_data = {
            "messageId": message.id,
            "sender_id": user.id,
            "type": message.media_type,
            "content": "",  # No text content for media messages
            "attachments": request.build_absolute_uri(message.media.url),
            "createdAt": format_to_ist(message.created_at)
        }

        # Broadcast via WebSocket as new_message event
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"chat_{room_id}",
            {
                "type": "new_message_broadcast",
                "data": message_data,
            }
        )

        # Broadcast inbox update to the other user
        other_user = room.user_a if room.user_b == user else room.user_b
        unseen_count = MessageReceipt.objects.filter(
            message__room_id=room_id,
            user_id=other_user.id,
            seen_at__isnull=True
        ).count()

        sender_data = {
            "id": user.id,
            "full_name": user.full_name,
            "profile_photo": user.profile_photo.url if user.profile_photo else None
        }

        inbox_update_data = {
            "room_id": room_id,
            "user": sender_data,
            "last_message": f"[{message.media_type.upper()} Message]",
            "last_message_time": format_to_ist(message.created_at),
            "unseen_count": unseen_count
        }

        async_to_sync(channel_layer.group_send)(
            f"inbox_{other_user.id}",
            {
                "type": "inbox_update_broadcast",
                "data": inbox_update_data,
            }
        )

        # Final API Response (also in standardized format)
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
from .tasks import expire_call, force_end_call
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
        expire_call.apply_async(
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
            notif_type="call_rejected",
            message="audio call rejected",
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

        # Allow ending calls in both "accepted" and "ringing" states
        allowed_states = ["accepted", "ringing"]
        if call.status not in allowed_states:
            return Response(
                {"error": f"Cannot end call in {call.status} state. "
                         f"Only calls in {allowed_states} can be ended."},
                status=400
            )

        print("\n📴 [CALL ENDED]")
        print("Call ID:", call.id)
        print("Ended by:", request.user.id)
        print("Previous status:", call.status)

        # Determine the final status based on current state
        if call.status == "ringing":
            # If call is ringing, mark it as "missed" or "cancelled"
            if request.user == call.caller:
                call.status = "cancelled"  # Caller cancelled before receiver answered
            else:
                call.status = "missed"  # Receiver declined/ended during ringing
        else:
            call.status = "ended"  # Normal end for accepted calls

        call.ended_at = timezone.now()
        call.save()

        other_user = (
            call.receiver if request.user == call.caller else call.caller
        )

        # Determine notification type based on final status
        if call.status == "cancelled":
            notif_type = "call_ended"
            message = "Call cancelled"
        elif call.status == "missed":
            notif_type = "call_missed"
            message = "Missed call"
        else:
            notif_type = "call_ended"
            message = "Call ended"

        create_notification(
            receiver=other_user,
            sender=request.user,
            notif_type=notif_type,
            message=message,
            extra_data={
                "call_id": str(call.id),
                "ended_by_id": str(request.user.id),
                "ended_by_name": request.user.full_name,
                "call_status": call.status
            }
        )

        return Response({
            "status": call.status,
            "call_id": call.id,
            "ended_by": request.user.id,
            "previous_status": call.status
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
            return Response({"error": "Unauthorized"}, status=403)

        if call.status in ["ended", "missed", "rejected"]:
            return Response(
                {"error": f"Call already {call.status}"},
                status=400
            )

        token = self._generate_token(call.channel_name, request.user.id)

        return Response({
            "token": token,
            "app_id": settings.AGORA_APP_ID,
            "uid": request.user.id,
            "channel_name": call.channel_name,
            "call_type": call.call_type,
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


# video call
class StartVideoCallAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        receiver_id = request.data.get("receiver_id")

        if not receiver_id:
            return Response({"error": "receiver_id required"}, status=400)

        try:
            receiver = CustomUser.objects.get(id=receiver_id)
        except CustomUser.DoesNotExist:
            return Response({"error": "Receiver not found"}, status=404)

        # Check if receiver is already in a call
        ongoing_calls = AudioCall.objects.filter(
            Q(caller=receiver) | Q(receiver=receiver)
        ).filter(
            status__in=["ringing", "accepted"],
            ended_at__isnull=True  # Most important: no end time
        ).exists()
        
        if ongoing_calls:
            return Response({
                "error": "User is currently in another call",
                "code": "user_busy"
            }, status=400)

        # Generate unique channel name
        channel_name = f"video_call_{uuid.uuid4().hex}"

        # Create video call
        call = AudioCall.objects.create(
            caller=request.user,
            receiver=receiver,
            call_type="video",
            channel_name=channel_name,
            status="ringing"
        )

        # Schedule auto-expire task (30 seconds for video)
        expire_call.apply_async(
            args=[call.id],
            countdown=getattr(settings, 'VIDEO_CALL_RING_TIMEOUT', 30)
        )

        # Generate token for caller
        caller_token = self._generate_token(channel_name, request.user.id)

        # Prepare caller video preview info
        caller_video_info = {
            "uid": str(request.user.id),
            "name": request.user.full_name,
            "has_video": True,
            "is_muted": False
        }

        # Notify receiver with video call data
        create_notification(
            receiver=receiver,
            sender=request.user,
            notif_type="incoming_video_call",
            message="Incoming video call",
            extra_data={
                "call_type": "video",
                "call_id": str(call.id),
                "channel_name": channel_name,
                "caller_id": str(request.user.id),
                "caller_name": request.user.full_name,
                "caller_video_info": caller_video_info,
                "app_id": settings.AGORA_APP_ID,
                "token": caller_token,  # Optional: send token for faster join
                "timestamp": timezone.now().isoformat()
            }
        )

        return Response({
            "status": "ringing",
            "call_type": "video",
            "call_id": call.id,
            "channel_name": channel_name,
            "app_id": settings.AGORA_APP_ID,
            "token": caller_token,
            "uid": request.user.id,
            "receiver_info": {
                "id": receiver.id,
                "name": receiver.full_name,
                # "avatar": receiver.avatar.url if receiver.avatar else None
            }
        })

    def _generate_token(self, channel_name, uid, role=1):
        """Generate Agora token with video privileges"""
        expire_time = 3600  # 1 hour
        current_time = int(time.time())
        privilege_expired_ts = current_time + expire_time

        token = RtcTokenBuilder.buildTokenWithUid(
            settings.AGORA_APP_ID,
            settings.AGORA_APP_CERTIFICATE,
            channel_name,
            uid,
            role,
            privilege_expired_ts
        )
        return token


class AcceptVideoCallAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        call_id = request.data.get("call_id")

        if not call_id:
            return Response({"error": "call_id required"}, status=400)

        try:
            call = AudioCall.objects.get(
                id=call_id,
                receiver=request.user,
                call_type="video"
            )
        except AudioCall.DoesNotExist:
            return Response(
                {"error": "Video call not found or unauthorized"},
                status=404
            )

        if call.status != "ringing":
            return Response(
                {"error": f"Call already {call.status}"},
                status=400
            )

        print(f"\n✅ [VIDEO CALL ACCEPTED] Call: {call.id}, User: {request.user.id}")

        # Update call state
        call.status = "accepted"
        call.accepted_at = timezone.now()
        call.save()

        force_end_call.apply_async(
        args=[call.id],
        countdown=getattr(settings, "MAX_VIDEO_CALL_DURATION", 3600)
        )

        # Generate token for receiver
        receiver_token = self._generate_token(call.channel_name, request.user.id)

        # Prepare receiver video info
        receiver_video_info = {
            "uid": str(request.user.id),
            "name": request.user.full_name,
            "has_video": True,
            "is_muted": False
        }

        # Notify caller
        create_notification(
            receiver=call.caller,
            sender=request.user,
            notif_type="video_call_accepted",
            message="Video call accepted",
            extra_data={
                "call_id": str(call.id),
                "call_type": "video",
                "channel_name": call.channel_name,
                "receiver_video_info": receiver_video_info,
                "token": receiver_token,  # Optional
                "timestamp": timezone.now().isoformat()
            }
        )

        return Response({
            "status": "accepted",
            "call_type": "video",
            "call_id": call.id,
            "app_id": settings.AGORA_APP_ID,
            "token": receiver_token,
            "channel_name": call.channel_name,
            "uid": request.user.id,
            "caller_info": {
                "id": call.caller.id,
                "name": call.caller.full_name,
                # "avatar": call.caller.avatar.url if call.caller.avatar else None
            }
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


class JoinVideoCallAPIView(APIView):
    """API for user to rejoin an ongoing video call"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        call_id = request.data.get("call_id")

        if not call_id:
            return Response({"error": "call_id required"}, status=400)

        try:
            call = AudioCall.objects.get(id=call_id, call_type="video")
        except AudioCall.DoesNotExist:
            return Response({"error": "Video call not found"}, status=404)

        # Authorization
        if request.user not in [call.caller, call.receiver]:
            return Response(
                {"error": "Unauthorized to join this call"},
                status=403
            )

        if call.status != "accepted":
            return Response(
                {"error": f"Call is {call.status}, cannot join"},
                status=400
            )

        # Generate fresh token
        token = self._generate_token(call.channel_name, request.user.id)

        # Get other user info
        other_user = call.caller if request.user == call.receiver else call.receiver
        
        # Check if other user is still in call
        other_user_in_call = (
            call.status == "accepted" and call.ended_at is None
        )

        print(f"\n🔗 [USER REJOINED VIDEO CALL] User: {request.user.id}, Call: {call.id}")

        return Response({
            "status": "rejoined",
            "call_type": "video",
            "call_id": call.id,
            "app_id": settings.AGORA_APP_ID,
            "token": token,
            "channel_name": call.channel_name,
            "uid": request.user.id,
            "other_user": {
                "id": other_user.id,
                "name": other_user.full_name,
                # "avatar": other_user.avatar.url if other_user.avatar else None,
                "in_call": other_user_in_call
            },
            "call_duration": self._get_call_duration(call)
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

    def _get_call_duration(self, call):
        if call.accepted_at:
            duration = timezone.now() - call.accepted_at
            return int(duration.total_seconds())
        return 0


class RejectVideoCallAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        call_id = request.data.get("call_id")
        reason = request.data.get("reason", "")

        if not call_id:
            return Response({"error": "call_id required"}, status=400)

        try:
            call = AudioCall.objects.get(
                id=call_id,
                receiver=request.user,
                call_type="video"
            )
        except AudioCall.DoesNotExist:
            return Response(
                {"error": "Video call not found or unauthorized"},
                status=404
            )

        if call.status != "ringing":
            return Response(
                {"error": f"Call already {call.status}"},
                status=400
            )

        print(f"\n❌ [VIDEO CALL REJECTED] Call: {call.id}, Reason: {reason}")

        call.status = "rejected"
        call.ended_at = timezone.now()
        call.save()

        # Notify caller
        create_notification(
            receiver=call.caller,
            sender=request.user,
            notif_type="video_call_rejected",
            message="Video call rejected",
            extra_data={
                "call_id": str(call.id),
                "call_type": "video",
                "reason": reason,
                "timestamp": timezone.now().isoformat()
            }
        )

        return Response({
            "status": "rejected",
            "call_id": call.id,
            "reason": reason
        })


class EndVideoCallAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        call_id = request.data.get("call_id")
        reason = request.data.get("reason", "normal_ending")

        if not call_id:
            return Response({"error": "call_id required"}, status=400)

        try:
            call = AudioCall.objects.get(id=call_id, call_type="video")
        except AudioCall.DoesNotExist:
            return Response({"error": "Video call not found"}, status=404)

        # Authorization
        if request.user not in [call.caller, call.receiver]:
            return Response(
                {"error": "Unauthorized to end this call"},
                status=403
            )

        if call.status == "ended":
            return Response({
                "status": "already_ended",
                "call_id": call.id
            })

        print(f"\n📴 [VIDEO CALL ENDED] Call: {call.id}, Ended by: {request.user.id}, Reason: {reason}")

        # Calculate call duration
        duration = 0
        if call.accepted_at:
            duration = int((timezone.now() - call.accepted_at).total_seconds())

        call.status = "ended"
        call.ended_at = timezone.now()
        call.save()

        # Notify other user
        other_user = call.receiver if request.user == call.caller else call.caller

        try:
            create_notification(
                receiver=other_user,
                sender=request.user,
                notif_type="video_call_ended",
                message="Video call ended",
                extra_data={
                    "call_id": str(call.id),
                    "call_type": "video",
                    "ended_by_id": str(request.user.id),
                    "ended_by_name": request.user.full_name,
                    "duration": duration,
                    "reason": reason,
                    "timestamp": timezone.now().isoformat()
                }
            )
        except Exception as e:
            # IMPORTANT: never crash API because of notifications
            print("⚠️ Notification failed (ignored):", str(e))


        return Response({
            "status": "ended",
            "call_id": call.id,
            "ended_by": request.user.id,
            "duration": duration,
            "reason": reason
        })



# call history 

class CallHistoryPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 50


class CallHistoryAPIView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = CallHistoryPagination

    def get(self, request):
        user = request.user

        calls = AudioCall.objects.filter(
            Q(caller=user) | Q(receiver=user)
        ).order_by("-started_at")

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(calls, request)

        serializer = CallHistorySerializer(
            page,
            many=True,
            context={"request": request}
        )

        return Response({
            "status": "200",
            "message": "Call history fetched successfully",
            "Response": {
                "count": paginator.page.paginator.count,
                "next": paginator.get_next_link(),
                "previous": paginator.get_previous_link(),
                "results": serializer.data
            }
        })
