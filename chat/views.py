from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .models import ChatRoom, Message, MessageReceipt
from .serializers import MessageSerializer, ChatRoomSerializer
from auth_api.models import CustomUser
from dating_backend.timezone_utils import format_to_ist


class MessagePagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


def _serialize_room(room, request):
    serializer = ChatRoomSerializer(room, context={"request": request})
    return serializer.data


def _paginate_messages(room, request):
    paginator = MessagePagination()
    messages_qs = (
        room.messages.select_related("sender", "room")
        .prefetch_related("receipts")
        .order_by("-created_at")
    )
    paginated = paginator.paginate_queryset(messages_qs, request)
    serializer = MessageSerializer(paginated, many=True, context={"request": request})
    return serializer.data[::-1], paginator


def _pagination_meta(paginator):
    page_obj = getattr(paginator, "page", None)
    if not page_obj:
        return 1, 1
    return page_obj.number, page_obj.paginator.num_pages


class GetOrCreateChatRoomView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        sender = request.user
        receiver_id = request.data.get("receiver_id")

        if not receiver_id:
            return Response(
                {"status": 400, "message": "receiver_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if str(receiver_id) == str(sender.id):
            return Response(
                {"status": 400, "message": "You cannot start a chat with yourself."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        receiver = get_object_or_404(CustomUser, id=receiver_id)

        participant_ids = sorted([sender.id, receiver.id])
        room = ChatRoom.objects.filter(
            user_a_id=participant_ids[0],
            user_b_id=participant_ids[1],
        ).first()
        created_new = False
        if not room:
            room = ChatRoom.objects.create(
                user_a_id=participant_ids[0],
                user_b_id=participant_ids[1],
            )
            created_new = True

        messages_data, paginator = _paginate_messages(room, request)

        page_number, total_pages = _pagination_meta(paginator)
        data = {
            "room": _serialize_room(room, request),
            "messages": messages_data,
            "page": page_number,
            "total_pages": total_pages,
        }

        return Response(
            {
                "status": 200,
                "message": "New chat room created" if created_new else "Chat room fetched successfully",
                "data": data,
            },
            status=status.HTTP_200_OK,
        )


class MessageListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, room_id):
        room = get_object_or_404(ChatRoom, id=room_id)
        if request.user.id not in {room.user_a_id, room.user_b_id}:
            return Response({"status": 403, "message": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)

        messages_data, paginator = _paginate_messages(room, request)
        page_number, total_pages = _pagination_meta(paginator)
        return Response(
            {
                "status": 200,
                "data": {
                    "room": _serialize_room(room, request),
                    "messages": messages_data,
                    "page": page_number,
                    "total_pages": total_pages,
                },
            }
        )


class SendMessageView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def post(self, request, room_id):
        room = get_object_or_404(ChatRoom, id=room_id)
        if request.user.id not in {room.user_a_id, room.user_b_id}:
            return Response({"status": 403, "message": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)

        content = request.data.get("content", "").strip()
        media_file = request.FILES.get("media")
        reply_to_id = request.data.get("reply_to")

        if not content and not media_file:
            return Response(
                {"status": 400, "message": "Either content or media is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        media_type = ""
        if media_file:
            content_type = media_file.content_type or ""
            if content_type.startswith("image/"):
                media_type = Message.MEDIA_IMAGE
            elif content_type.startswith("video/"):
                media_type = Message.MEDIA_VIDEO
            else:
                return Response(
                    {"status": 400, "message": "Unsupported media type. Only images or videos are allowed."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        message = Message(room=room, sender=request.user, media=media_file, media_type=media_type)
        if content:
            message.content = content
        if reply_to_id:
            try:
                message.reply_to = room.messages.get(id=reply_to_id)
            except Message.DoesNotExist:
                return Response({"status": 404, "message": "Reply target not found."}, status=status.HTTP_404_NOT_FOUND)
        message.save()

        now = timezone.now()
        receipts = []
        for user in (room.user_a, room.user_b):
            receipt, _ = MessageReceipt.objects.get_or_create(message=message, user=user)
            if user.id == request.user.id:
                receipt.delivered_at = now
                receipt.seen_at = now
                receipt.save(update_fields=["delivered_at", "seen_at"])
            receipts.append(receipt)

        response_serializer = MessageSerializer(message, context={"request": request})
        payload = response_serializer.data
        broadcast_payload = MessageSerializer(message).data

        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f"chat_{room.id}",
                {"type": "chat.message", "payload": broadcast_payload},
            )

        return Response({"status": 201, "message": "Message sent", "data": payload}, status=status.HTTP_201_CREATED)


class MarkMessagesSeenView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, room_id):
        room = get_object_or_404(ChatRoom, id=room_id)
        if request.user.id not in {room.user_a_id, room.user_b_id}:
            return Response({"status": 403, "message": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)

        message_ids = request.data.get("message_ids")
        filters = {"message__room": room, "user": request.user, "seen_at__isnull": True}
        if message_ids:
            filters["message_id__in"] = message_ids

        now = timezone.now()
        receipts = list(MessageReceipt.objects.filter(**filters))
        if not receipts:
            return Response({"status": 200, "message": "Nothing to update"})

        for receipt in receipts:
            receipt.delivered_at = receipt.delivered_at or now
            receipt.seen_at = now
            receipt.save(update_fields=["delivered_at", "seen_at"])

        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f"chat_{room.id}",
                {
                    "type": "chat.receipt",
                    "payload": {
                        "message_ids": [r.message_id for r in receipts],
                        "seen_at": format_to_ist(now),
                        "user_id": request.user.id,
                    },
                },
            )

        return Response({"status": 200, "message": "Receipts updated"})
