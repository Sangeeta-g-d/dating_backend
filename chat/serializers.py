from rest_framework import serializers
from .models import Message, ChatRoom, AudioCall
from dating_backend.timezone_utils import format_to_ist  # Import the utility
from admin_part.models import ChatBackground

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
    
class ChatBackgroundSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ChatBackground
        fields = ['id', 'name', 'image_url']

    def get_image_url(self, obj):
        request = self.context.get("request")
        if obj.image:
            return request.build_absolute_uri(obj.image.url)
        return None



# call history 
class CallHistorySerializer(serializers.ModelSerializer):
    caller_name = serializers.CharField(source="caller.full_name", read_only=True)
    receiver_name = serializers.CharField(source="receiver.full_name", read_only=True)

    caller_profile_photo = serializers.SerializerMethodField()
    receiver_profile_photo = serializers.SerializerMethodField()

    started_at = serializers.SerializerMethodField()
    accepted_at = serializers.SerializerMethodField()
    ended_at = serializers.SerializerMethodField()

    duration = serializers.IntegerField(read_only=True)
    call_direction = serializers.SerializerMethodField()

    class Meta:
        model = AudioCall
        fields = [
            "id",
            "call_type",
            "status",
            "call_direction",   # ✅ NEW
            "channel_name",

            "caller_name",
            "receiver_name",
            "caller_profile_photo",
            "receiver_profile_photo",

            "started_at",
            "accepted_at",
            "ended_at",
            "duration",
        ]

    def get_call_direction(self, obj):
        request = self.context.get("request")
        if request and request.user == obj.caller:
            return "outgoing"
        return "incoming"

    def get_started_at(self, obj):
        return format_to_ist(obj.started_at)

    def get_accepted_at(self, obj):
        return format_to_ist(obj.accepted_at)

    def get_ended_at(self, obj):
        return format_to_ist(obj.ended_at)

    def get_caller_profile_photo(self, obj):
        request = self.context.get("request")
        if obj.caller.profile_photo:
            return request.build_absolute_uri(obj.caller.profile_photo.url)
        return None

    def get_receiver_profile_photo(self, obj):
        request = self.context.get("request")
        if obj.receiver.profile_photo:
            return request.build_absolute_uri(obj.receiver.profile_photo.url)
        return None
