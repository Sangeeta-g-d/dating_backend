from rest_framework import serializers
from .models import Message, ChatRoom
from dating_backend.timezone_utils import format_to_ist  # ✅ import the utility
from rest_framework import serializers
from .models import ChatRoom, Message

class MessageSerializer(serializers.ModelSerializer):
    sender = serializers.SerializerMethodField()
    content = serializers.CharField(source="content", read_only=True)

    class Meta:
        model = Message
        fields = [
            "id",
            "sender",
            "content",
            "media",
            "media_type",
            "reply_to",
            "created_at",
            "is_deleted",
        ]

    def get_sender(self, obj):
        request = self.context.get("request")
        if request and request.user.id == obj.sender_id:
            return "you"
        return obj.sender.full_name or obj.sender.email


class ChatRoomSerializer(serializers.ModelSerializer):
    participants = serializers.SerializerMethodField()

    class Meta:
        model = ChatRoom
        fields = [
            "id",
            "participants",
            "created_at",
            "updated_at",
        ]

    def get_participants(self, obj):
        request = self.context.get("request")
        user_a = obj.user_a
        user_b = obj.user_b
        current_user = request.user if request else None

        def format_user(user):
            if current_user and user.id == current_user.id:
                return {
                    "id": user.id,
                    "label": "you",
                    "full_name": "you",
                    "email": user.email,
                }
            return {
                "id": user.id,
                "label": user.full_name or user.email,
                "full_name": user.full_name,
                "email": user.email,
            }

        return [format_user(user_a), format_user(user_b)]
