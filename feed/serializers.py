from rest_framework import serializers
from .models import *
from dating_backend.timezone_utils import format_to_ist  # Utility to format datetime to IST
from auth_api.models import UserProfile, Interest
import os
from auth_api.models import CustomUser
from swipe_feature.models import Match
import uuid
from django.core.files.storage import default_storage

class PostCreateSerializer(serializers.ModelSerializer):
    media = serializers.ListField(
        child=serializers.FileField(allow_empty_file=False, use_url=False),
        write_only=True,
        required=False
    )

    class Meta:
        model = Post
        fields = ['caption', 'media']

    def create(self, validated_data):
        user = self.context['request'].user
        media_files = validated_data.pop('media', [])
        media_urls = []

        for file in media_files:
            # Generate unique filename
            ext = os.path.splitext(file.name)[1]
            unique_filename = f"{uuid.uuid4().hex}{ext}"
            
            # Save to S3 (automatically uses your MediaStorage backend)
            path = default_storage.save(f"posts/{unique_filename}", file)
            
            # Get full URL
            url = default_storage.url(path)
            media_urls.append(url)

        # Create post with S3 URLs
        post = Post.objects.create(
            user=user,
            caption=validated_data.get('caption', ''),
            media=media_urls
        )
        return post
    

class CommentReplySerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ["id", "user", "content", "created_at"]

    def get_user(self, obj):
        return {
            "id": obj.user.id,
            "full_name": obj.user.full_name,
            "profile_photo": obj.user.profile_photo.url if obj.user.profile_photo else None,
        }

    def get_created_at(self, obj):
        return format_to_ist(obj.created_at)
    



class CommentSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    replies = CommentReplySerializer(many=True, read_only=True)
    created_at = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ["id", "user", "content", "created_at", "replies"]

    def get_user(self, obj):
        return {
            "id": obj.user.id,
            "full_name": obj.user.full_name,
            "profile_photo": obj.user.profile_photo.url if obj.user.profile_photo else None,
        }

    def get_created_at(self, obj):
        return format_to_ist(obj.created_at)


class PostSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    total_likes = serializers.SerializerMethodField()
    total_comments = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()
    media = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            "id",
            "user",
            "caption",
            "media",
            "created_at",
            "total_likes",
            "total_comments",
            "is_liked",
        ]

    def get_media(self, obj):
        """Convert stored relative paths into full URLs"""
        request = self.context.get("request")
        if not obj.media:
            return []
        return [request.build_absolute_uri(settings.MEDIA_URL + path) for path in obj.media]

    def get_user(self, obj):
        request = self.context.get("request")
        current_user = self.context.get("current_user")
        user = obj.user

        # If the post belongs to the logged-in user, show "You"
        full_name = "You" if current_user and user == current_user else user.full_name

        profile_photo_url = (
            request.build_absolute_uri(user.profile_photo.url)
            if user.profile_photo
            else None
        )

        return {
            "id": user.id,
            "full_name": full_name,
            "profile_photo": profile_photo_url,
        }

    def get_total_likes(self, obj):
        return obj.total_likes()

    def get_total_comments(self, obj):
        return obj.total_comments()

    def get_is_liked(self, obj):
        user = self.context.get('request').user
        return obj.likes.filter(user=user).exists()

    def get_created_at(self, obj):
        from dating_backend.timezone_utils import format_to_ist
        return format_to_ist(obj.created_at)



class CommentSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    replies = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            "id",
            "user",
            "content",
            "created_at",
            "replies",
        ]

    def get_user(self, obj):
        return {
            "id": obj.user.id,
            "full_name": obj.user.full_name,
            "profile_photo": obj.user.profile_photo.url if obj.user.profile_photo else None,
        }

    def get_replies(self, obj):
        replies = obj.replies.all().order_by('created_at')
        return CommentSerializer(replies, many=True, context=self.context).data

    def get_created_at(self, obj):
        return format_to_ist(obj.created_at)


class InterestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Interest
        fields = ['id', 'name']



class UserPostSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    profile_photo = serializers.ImageField(source='user.profile_photo', read_only=True)
    total_likes = serializers.SerializerMethodField()
    total_comments = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField() 

    class Meta:
        model = Post
        fields = [
            'id',
            'user_name',
            'profile_photo',
            'caption',
            'media',
            'total_likes',
            'total_comments',
            'created_at',
        ]

    def get_total_likes(self, obj):
        return obj.total_likes()

    def get_total_comments(self, obj):
        return obj.total_comments()
    
    def get_created_at(self, obj):
        """Return created_at in IST formatted style"""
        return format_to_ist(obj.created_at)

    
class UserProfileSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    profile_photo = serializers.ImageField(source='user.profile_photo', read_only=True)
    interests = InterestSerializer(many=True, read_only=True)
    matches_count = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = [
            'user_name', 'email', 'profile_photo', 'bio', 'gender', 'date_of_birth',
            'height', 'marital_status', 'mother_tongue', 'religion', 'occupation',
            'looking_for', 'would_like_to_meet', 'interests', 'matches_count'
        ]

    def get_matches_count(self, obj):
        """Return total number of matches for this user"""
        return Match.objects.filter(
            models.Q(user1=obj.user) | models.Q(user2=obj.user)
        ).count()


class UserMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ["id", "full_name", "profile_photo"]