from rest_framework import serializers
from .models import *
from django.contrib.auth import authenticate
from admin_part.models import Interest
from feed.models import Post

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = CustomUser
        fields = ["id", "full_name", "email", "phone_number", "profile_photo", "city", "state", "country", "password"]

    def create(self, validated_data):
        print("🔍 DEBUG - Serializer create method called")
        print(f"🔍 DEBUG - Validated data keys: {validated_data.keys()}")
        
        if 'profile_photo' in validated_data:
            print(f"🔍 DEBUG - Profile photo in validated_data: {validated_data['profile_photo']}")
        
        password = validated_data.pop("password")
        
        # Extract profile_photo separately
        profile_photo = validated_data.pop('profile_photo', None)
        
        # Create user without profile_photo first
        user = CustomUser.objects.create_user(**validated_data)
        user.set_password(password)
        
        # Add profile_photo after user is created
        if profile_photo:
            user.profile_photo = profile_photo
            print(f"🔍 DEBUG - Setting profile_photo on user: {profile_photo.name}")
        
        user.save()
        print(f"🔍 DEBUG - User saved, profile_photo: {getattr(user, 'profile_photo', None)}")
        
        return user


class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data.get("email")
        password = data.get("password")

        if email and password:
            user = authenticate(request=self.context.get("request"), email=email, password=password)
            if not user:
                raise serializers.ValidationError("Invalid email or password")
        else:
            raise serializers.ValidationError("Both email and password are required")

        data["user"] = user
        return data
    
    
class SendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()


class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)

# fetch interests
class InterestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Interest
        fields = ['id', 'name']


# post user details
class UserProfileSerializer(serializers.ModelSerializer):
    interests = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Interest.objects.all(), required=False
    )

    class Meta:
        model = UserProfile
        fields = [
            'bio',
            'gender',
            'would_like_to_meet',
            'date_of_birth',
            'height',
            'marital_status',
            'mother_tongue',
            'religion',
            'occupation',
            'looking_for',
            'interests',
            'latitude',
            'longitude',
        ]

    def create(self, validated_data):
        interests = validated_data.pop('interests', [])
        user = self.context['request'].user
        profile, _ = UserProfile.objects.get_or_create(user=user)
        for attr, value in validated_data.items():
            setattr(profile, attr, value)
        profile.save()
        if interests:
            profile.interests.set(interests)
        return profile
    

class DeviceTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceToken
        fields = ['device_type', 'fcm_token']


class UserDetailsSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="user.full_name", required=False)
    phone_number = serializers.CharField(source="user.phone_number", required=False, allow_null=True, allow_blank=True)
    profile_photo = serializers.ImageField(source="user.profile_photo", required=False, allow_null=True)
    city = serializers.CharField(source="user.city", required=False, allow_null=True, allow_blank=True)
    state = serializers.CharField(source="user.state", required=False, allow_null=True, allow_blank=True)
    country = serializers.CharField(source="user.country", required=False, allow_null=True, allow_blank=True)

    # 👇 Show interest names while still allowing updates via IDs
    interests = serializers.SerializerMethodField()
    interest_ids = serializers.PrimaryKeyRelatedField(
        source="interests", many=True, queryset=Interest.objects.all(),
        write_only=True, required=False
    )

    class Meta:
        model = UserProfile
        exclude = ["user"]

    def get_interests(self, obj):
        """Return list of interests with id and name"""
        return [{"id": interest.id, "name": interest.name} for interest in obj.interests.all()]

    def update(self, instance, validated_data):
        """Handle nested user updates and profile updates"""
        user_data = validated_data.pop("user", {})
        interests_data = validated_data.pop("interests", None)
        user = instance.user

        # Update user fields
        for attr, value in user_data.items():
            setattr(user, attr, value)
        user.save()

        # Update profile fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update interests if provided
        if interests_data is not None:
            instance.interests.set(interests_data)

        return instance


# fetch logged in user posts
class PostSerializer(serializers.ModelSerializer):
    total_likes = serializers.IntegerField(source='total_likes', read_only=True)
    total_comments = serializers.IntegerField(source='total_comments', read_only=True)

    class Meta:
        model = Post
        fields = [
            'id', 'caption', 'media', 'created_at', 'updated_at',
            'total_likes', 'total_comments'
        ]