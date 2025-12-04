from rest_framework import serializers
from .models import Message, ChatRoom
from dating_backend.timezone_utils import format_to_ist  # Import the utility

class MessageSerializer(serializers.ModelSerializer):
    sender = serializers.SerializerMethodField()
    content = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()
    is_seen = serializers.SerializerMethodField() 

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
            "is_seen"
        ]

    def get_is_seen(self, obj):
        request = self.context.get("request")
        user = request.user
        
        receipt = obj.receipts.filter(user=user).first()
        return bool(receipt and receipt.seen_at)

    def get_sender(self, obj):
        request = self.context.get("request")
        if request and request.user.id == obj.sender_id:
            return "you"
        return obj.sender.full_name or obj.sender.email

    def get_content(self, obj):
        """Return decrypted content"""
        return obj.content  # This uses the @property decorator

    def get_created_at(self, obj):
        """Format created_at timestamp using IST timezone"""
        return format_to_ist(obj.created_at)


class ChatRoomSerializer(serializers.ModelSerializer):
    participants = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()
    updated_at = serializers.SerializerMethodField()
    last_message_at = serializers.SerializerMethodField()

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
            # Build absolute URL for profile photo if it exists
            profile_photo_url = None
            if user.profile_photo:
                if request:
                    profile_photo_url = request.build_absolute_uri(user.profile_photo.url)
                else:
                    profile_photo_url = user.profile_photo.url
            
            if current_user and user.id == current_user.id:
                return {
                    "id": user.id,
                    "full_name": "you",
                    "profile_photo": profile_photo_url,
                }
            return {
                "id": user.id,
                "full_name": user.full_name,
                "profile_photo": profile_photo_url,
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

    def get_created_at(self, obj):
        """Format created_at timestamp using IST timezone"""
        return format_to_ist(obj.created_at)

    def get_updated_at(self, obj):
        """Format updated_at timestamp using IST timezone"""
        return format_to_ist(obj.updated_at)

    def get_last_message_at(self, obj):
        """Format last_message_at timestamp using IST timezone"""
        return format_to_ist(obj.last_message_at)