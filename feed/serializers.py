from rest_framework import serializers
from .models import *
from dating_backend.timezone_utils import format_to_ist  # Utility to format datetime to IST
from auth_api.models import UserProfile, Interest
import os
from auth_api.models import CustomUser
from swipe_feature.models import Match
import uuid
from django.core.files.storage import default_storage

from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
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
        media_paths = []  # Changed from media_urls to media_paths

        for file in media_files:
            file_extension = os.path.splitext(file.name)[1]
            file_name = f"{uuid.uuid4().hex}{file_extension}"
            file_path = f"posts/{file_name}"
            
            # Save to S3
            saved_path = default_storage.save(file_path, ContentFile(file.read()))
            
            # ✅ Store only the relative path, NOT the full URL
            media_paths.append(saved_path)  # Will be: posts/205220fa...jpeg

        post = Post.objects.create(
            user=user, 
            media=media_paths,  # Stores: ["posts/file1.jpg", "posts/file2.jpg"]
            **validated_data
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

from django.core.files.storage import default_storage

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
        """Convert stored relative paths into full S3 URLs"""
        if not obj.media:
            return []
        
        # Use default_storage to build S3 URLs from relative paths
        media_urls = []
        for path in obj.media:
            # default_storage.url() will generate full S3 URL
            # e.g., posts/file.jpg -> https://bucket.s3.region.amazonaws.com/media/posts/file.jpg
            full_url = default_storage.url(path)
            media_urls.append(full_url)
        
        return media_urls

    def get_user(self, obj):
        current_user = self.context.get("current_user")
        user = obj.user

        # If the post belongs to the logged-in user, show "You"
        full_name = "You" if current_user and user == current_user else user.full_name

        # Handle profile photo URL properly
        profile_photo_url = None
        if user.profile_photo:
            # If profile_photo is a FileField/ImageField stored on S3
            profile_photo_url = user.profile_photo.url
            # This will automatically use your S3 storage backend

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
        if user and user.is_authenticated:
            return obj.likes.filter(user=user).exists()
        return False

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
    profile_photo = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = ["id", "full_name", "profile_photo"]

    def get_profile_photo(self, obj):
        request = self.context.get("request")
        if obj.profile_photo:
            return request.build_absolute_uri(obj.profile_photo.url)
        return None

class PostDetailSerializer(serializers.ModelSerializer):
    user = UserMiniSerializer(read_only=True)
    media = serializers.SerializerMethodField()  # <--- updated
    likes_count = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            "id",
            "user",
            "caption",
            "media",
            "created_at",
            "likes_count",
            "comments_count",
            "is_liked",
        ]

    def get_media(self, obj):
        """
        Convert list of relative media paths into full absolute URLs.
        """
        request = self.context.get("request")
        media_files = obj.media or []

        full_urls = []
        for path in media_files:
            if path.startswith("http"):
                full_urls.append(path)  # already absolute
            else:
                full_urls.append(request.build_absolute_uri(path))

        return full_urls

    def get_created_at(self, obj):
        return format_to_ist(obj.created_at)

    def get_likes_count(self, obj):
        return obj.likes.count()

    def get_comments_count(self, obj):
        return obj.comments.count()

    def get_is_liked(self, obj):
        user = self.context["request"].user
        return Like.objects.filter(post=obj, user=user).exists()
