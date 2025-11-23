from rest_framework import serializers
from .models import StoryModel
from dating_backend.timezone_utils import format_to_ist  # ✅ Import your helper function
from auth_api.models import CustomUser
class StorySerializer(serializers.ModelSerializer):
    media_url = serializers.SerializerMethodField()
    created_at_ist = serializers.SerializerMethodField()
    expires_at_ist = serializers.SerializerMethodField()

    class Meta:
        model = StoryModel
        fields = ['id', 'content_text', 'media', 'media_url', 'created_at_ist', 'expires_at_ist']
        read_only_fields = ['created_at_ist', 'expires_at_ist']

    def get_media_url(self, obj):
        request = self.context.get('request')
        if obj.media and hasattr(obj.media, 'url') and request:
            return request.build_absolute_uri(obj.media.url)
        return None

    def get_created_at_ist(self, obj):
        # ✅ Use universal timezone utility
        return format_to_ist(obj.created_at)

    def get_expires_at_ist(self, obj):
        # ✅ Use universal timezone utility
        return format_to_ist(obj.expires_at)


class FetchStorySerializer(serializers.ModelSerializer):
    media_url = serializers.SerializerMethodField()
    created_at_ist = serializers.SerializerMethodField()
    expires_at_ist = serializers.SerializerMethodField()
    user_full_name = serializers.SerializerMethodField()
    user_profile_photo = serializers.SerializerMethodField()
    views_count = serializers.SerializerMethodField()
    class Meta:
        model = StoryModel
        fields = [
            'id',
            'content_text',
            'media',
            'media_url',
            'created_at_ist',
            'expires_at_ist',
            'user_full_name',
            'user_profile_photo',
            'views_count'
        ]
        read_only_fields = ['created_at_ist', 'expires_at_ist']

    def get_media_url(self, obj):
        request = self.context.get('request')
        if obj.media and hasattr(obj.media, 'url') and request:
            return request.build_absolute_uri(obj.media.url)
        return None

    def get_created_at_ist(self, obj):
        return format_to_ist(obj.created_at)

    def get_expires_at_ist(self, obj):
        return format_to_ist(obj.expires_at)

    def get_user_full_name(self, obj):
        return obj.user.full_name if obj.user else None

    def get_user_profile_photo(self, obj):
        request = self.context.get('request')
        if obj.user and obj.user.profile_photo and hasattr(obj.user.profile_photo, 'url') and request:
            return request.build_absolute_uri(obj.user.profile_photo.url)
        return None
    
    def get_views_count(self, obj):
        return obj.views.count()
    
class StoryViewerSerializer(serializers.ModelSerializer):
    profile_photo = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = ["id", "full_name", "profile_photo"]

    def get_profile_photo(self, obj):
        request = self.context.get("request")
        if obj.profile_photo:
            return request.build_absolute_uri(obj.profile_photo.url)
        return None
