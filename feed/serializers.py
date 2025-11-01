from rest_framework import serializers
from .models import *
from dating_backend.timezone_utils import format_to_ist  # Utility to format datetime to IST
from auth_api.models import UserProfile, Interest
import os

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
        upload_path = os.path.join(settings.MEDIA_ROOT, 'posts')
        os.makedirs(upload_path, exist_ok=True)

        for file in media_files:
            file_name = file.name
            file_path = os.path.join(upload_path, file_name)

            # Save file
            with open(file_path, 'wb+') as destination:
                for chunk in file.chunks():
                    destination.write(chunk)

            # Save relative URL for JSONField
            media_urls.append(f"posts/{file_name}")

        post = Post.objects.create(user=user, media=media_urls, **validated_data)
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
    likes_count = serializers.IntegerField(source='total_likes', read_only=True)
    comments_count = serializers.IntegerField(source='total_comments', read_only=True)
    created_at = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = ['id', 'caption', 'image', 'video', 'likes_count', 'comments_count', 'created_at']

    def get_created_at(self, obj):
        return format_to_ist(obj.created_at)
    
class UserProfileSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    profile_photo = serializers.ImageField(source='user.profile_photo', read_only=True)
    interests = InterestSerializer(many=True, read_only=True)
    followers_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = [
            'user_name', 'email', 'profile_photo', 'bio', 'gender', 'date_of_birth',
            'height', 'marital_status', 'mother_tongue', 'religion', 'occupation',
            'looking_for', 'would_like_to_meet', 'interests', 'followers_count', 'following_count'
        ]

    def get_followers_count(self, obj):
        return obj.user.followers.count() if hasattr(obj.user, 'followers') else 0

    def get_following_count(self, obj):
        return obj.user.following.count() if hasattr(obj.user, 'following') else 0
    

class UserMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = settings.AUTH_USER_MODEL
        fields = ["id", "full_name", "profile_photo"]

