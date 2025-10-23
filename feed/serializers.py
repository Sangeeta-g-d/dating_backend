from rest_framework import serializers
from .models import *
from dating_backend.timezone_utils import format_to_ist  # Utility to format datetime to IST
from auth_api.models import UserProfile, Interest


class PostCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Post
        fields = ['caption', 'image', 'video']

    def create(self, validated_data):
        user = self.context['request'].user
        post = Post.objects.create(user=user, **validated_data)
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
    total_likes = serializers.IntegerField(source="total_likes", read_only=True)
    total_comments = serializers.IntegerField(source="total_comments", read_only=True)
    comments = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            "id",
            "user",
            "caption",
            "image",
            "video",
            "created_at",
            "total_likes",
            "total_comments",
            "comments",
        ]

    def get_user(self, obj):
        return {
            "id": obj.user.id,
            "full_name": obj.user.full_name,
            "profile_photo": obj.user.profile_photo.url if obj.user.profile_photo else None,
        }

    def get_comments(self, obj):
        # Only top-level comments (exclude replies)
        comments = obj.comments.filter(parent__isnull=True).order_by('-created_at')
        return CommentSerializer(comments, many=True).data

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

