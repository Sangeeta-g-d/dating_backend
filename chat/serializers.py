from rest_framework import serializers
from .models import Message, ChatRoom
from django.utils import timezone

class MessageSerializer(serializers.ModelSerializer):
    sender = serializers.SerializerMethodField()
    content = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()

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

    def get_content(self, obj):
        """Return decrypted content"""
        return obj.content  # This uses the @property decorator

    def get_created_at(self, obj):
        """Format created_at timestamp"""
        return obj.created_at.isoformat() if obj.created_at else None


class ChatRoomSerializer(serializers.ModelSerializer):
    participants = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = ChatRoom
        fields = [
            "id",
            "participants",
            "created_at",
            "updated_at",
            "last_message_at",
            "last_message",
            "unread_count",
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

    def get_last_message(self, obj):
        """Get the last message in the chat room"""
        last_message = obj.messages.order_by('-created_at').first()
        if last_message:
            return MessageSerializer(last_message, context=self.context).data
        return None

    def get_unread_count(self, obj):
        """Get unread message count for current user"""
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.messages.exclude(sender=request.user).filter(
                receipts__user=request.user,
                receipts__seen_at__isnull=True
            ).count()
        return 0