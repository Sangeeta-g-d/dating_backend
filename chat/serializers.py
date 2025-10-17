from rest_framework import serializers
from .models import Message
from dating_backend.timezone_utils import format_to_ist  # ✅ import the utility

class MessageSerializer(serializers.ModelSerializer):
    sender = serializers.SerializerMethodField()
    content = serializers.CharField(source="content")
    timestamp = serializers.SerializerMethodField()  # ✅ override timestamp formatting

    class Meta:
        model = Message
        fields = ["id", "sender", "content", "timestamp", "is_seen", "is_deleted"]

    def get_sender(self, obj):
        request = self.context.get("request")
        if request and hasattr(request, "user") and obj.sender == request.user:
            return "You"
        return getattr(obj.sender, "full_name", obj.sender.email)

    def get_timestamp(self, obj):
        """Return formatted timestamp in IST."""
        return format_to_ist(obj.timestamp)
