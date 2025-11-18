from rest_framework import serializers
from .models import Message, ChatRoom
from dating_backend.timezone_utils import format_to_ist  # ✅ import the utility


class ChatRoomSerializer(serializers.ModelSerializer):
    participants = serializers.SerializerMethodField()
    last_message_at = serializers.SerializerMethodField()

    class Meta:
        model = ChatRoom
        fields = ["id", "participants", "last_message_at"]

    def get_participants(self, obj):
        return [
            {
                "id": obj.user_a.id,
                "email": obj.user_a.email,
                "full_name": obj.user_a.full_name,
            },
            {
                "id": obj.user_b.id,
                "email": obj.user_b.email,
                "full_name": obj.user_b.full_name,
            },
        ]

    def get_last_message_at(self, obj):
        if obj.last_message_at:
            return format_to_ist(obj.last_message_at)
        return None


class MessageSerializer(serializers.ModelSerializer):
    sender = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()
    content = serializers.SerializerMethodField()
    media_url = serializers.SerializerMethodField()
    timestamp = serializers.SerializerMethodField()
    delivered_at = serializers.SerializerMethodField()
    seen_at = serializers.SerializerMethodField()
    reply_to = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            "id",
            "room_id",
            "sender",
            "is_mine",
            "content",
            "media_url",
            "media_type",
            "reply_to",
            "timestamp",
            "delivered_at",
            "seen_at",
            "is_deleted",
            "is_system",
        ]

    def _get_viewer(self):
        viewer = self.context.get("viewer")
        if viewer is not None:
            return viewer
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            return request.user
        return None

    def get_sender(self, obj):
        return {
            "id": obj.sender_id,
            "email": getattr(obj.sender, "email", ""),
            "full_name": getattr(obj.sender, "full_name", obj.sender.email),
        }

    def get_is_mine(self, obj):
        viewer = self._get_viewer()
        if viewer is None:
            return False
        return obj.sender_id == getattr(viewer, "id", None)

    def get_content(self, obj):
        return obj.content

    def get_media_url(self, obj):
        request = self.context.get("request")
        if obj.media:
            if request:
                return request.build_absolute_uri(obj.media.url)
            return obj.media.url
        return None

    def get_timestamp(self, obj):
        return format_to_ist(obj.created_at)

    def _get_relevant_receipt(self, obj):
        viewer = self._get_viewer()
        if not viewer:
            return None
        if obj.sender_id == viewer.id:
            other = obj.room.user_a if obj.room.user_a_id != viewer.id else obj.room.user_b
            return obj.receipts.filter(user=other).first()
        return obj.receipts.filter(user=viewer).first()

    def get_delivered_at(self, obj):
        receipt = self._get_relevant_receipt(obj)
        if receipt and receipt.delivered_at:
            return format_to_ist(receipt.delivered_at)
        return None

    def get_seen_at(self, obj):
        receipt = self._get_relevant_receipt(obj)
        if receipt and receipt.seen_at:
            return format_to_ist(receipt.seen_at)
        return None

    def get_reply_to(self, obj):
        if obj.reply_to:
            return {
                "id": obj.reply_to_id,
                "content": obj.reply_to.content,
                "is_deleted": obj.reply_to.is_deleted,
            }
        return None
