from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone
import random
from datetime import date
from datetime import timedelta
from django.conf import settings
from admin_part.models import Interest
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin

# Custom User Manager
class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


# Custom User Model
class CustomUser(AbstractBaseUser, PermissionsMixin):
    full_name = models.CharField(max_length=150)
    email = models.EmailField(unique=True, max_length=255)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    profile_photo = models.ImageField(upload_to="profile_photos/", blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    # Daily swipe tracking
    swipes_today = models.PositiveIntegerField(default=0)
    last_swipe_reset = models.DateField(default=timezone.now)

    objects = CustomUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email

    # ----- SWIPE LIMIT METHODS -----
    def can_swipe(self):
        """Check if user can swipe today"""
        # Reset daily swipes if day changed
        if self.last_swipe_reset != date.today():
            self.swipes_today = 0
            self.last_swipe_reset = date.today()
            self.save(update_fields=['swipes_today', 'last_swipe_reset'])

        # Unlimited swipes for premium users
        if hasattr(self, 'subscription') and self.subscription.plan and self.subscription.plan.swipe_limit is None:
            return True

        # Limited swipes
        limit = self.subscription.plan.swipe_limit if hasattr(self, 'subscription') and self.subscription.plan else 10
        return self.swipes_today < limit

    def increment_swipes(self):
        """Increment swipe count after a swipe"""
        self.swipes_today += 1
        self.save(update_fields=['swipes_today'])

class EmailOTP(models.Model):
    email = models.EmailField()
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)

    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(minutes=5)  # OTP valid for 5 mins

    @staticmethod
    def generate_otp():
        return str(random.randint(100000, 999999))


class UserProfile(models.Model):
    GENDER_CHOICES = [
        ("male", "Male"),
        ("female", "Female"),
        ("other", "Other"),
    ]

    MEET_PREFERENCE_CHOICES = [
        ("male", "Male"),
        ("female", "Female"),
        ("everyone", "Everyone"),
    ]

    MARITAL_STATUS_CHOICES = [
        ("single", "Single"),
        ("divorced", "Divorced"),
        ("widowed", "Widowed"),
        ("in_a_relationship", "In a Relationship"),
    ]

    RELIGION_CHOICES = [
        ("hindu", "Hindu"),
        ("muslim", "Muslim"),
        ("christian", "Christian"),
        ("sikh", "Sikh"),
        ("buddhist", "Buddhist"),
        ("jain", "Jain"),
        ("other", "Other"),
    ]

    LOOKING_FOR_CHOICES = [
        ("friendship", "Friendship"),
        ("casual_dating", "Casual Dating"),
        ("serious_relationship", "Serious Relationship"),
        ("marriage", "Marriage"),
        ("networking", "Networking"),
    ]

    user = models.OneToOneField("CustomUser", on_delete=models.CASCADE, related_name="profile")
    bio = models.TextField(blank=True, null=True)
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES)
    would_like_to_meet = models.CharField(
        max_length=20, choices=MEET_PREFERENCE_CHOICES, default="everyone"
    )

    date_of_birth = models.DateField(blank=True, null=True)
    height = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True, help_text="Height in cm")
    marital_status = models.CharField(
        max_length=20, choices=MARITAL_STATUS_CHOICES, blank=True, null=True
    )
    mother_tongue = models.CharField(max_length=50, blank=True, null=True)
    religion = models.CharField(max_length=50, choices=RELIGION_CHOICES, blank=True, null=True)

    occupation = models.CharField(max_length=100, blank=True, null=True)
    looking_for = models.CharField(max_length=30, choices=LOOKING_FOR_CHOICES, blank=True, null=True)

    interests = models.ManyToManyField(Interest, related_name="users", blank=True)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)
    last_active = models.DateTimeField(default=timezone.now)
    is_online = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.full_name}'s Profile"
    


class DeviceToken(models.Model):
    DEVICE_CHOICES = [
        ("android", "Android"),
        ("ios", "iOS"),
    ]

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="device_tokens")
    device_type = models.CharField(max_length=10, choices=DEVICE_CHOICES)
    fcm_token = models.CharField(max_length=512)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "fcm_token")  # prevents duplicates

    def __str__(self):
        return f"{self.user.email} - {self.device_type}"