from django.db import models
from django.conf import settings
from django.utils import timezone       # for timezone.now()
from datetime import timedelta, date   
# Create your models here.

User = settings.AUTH_USER_MODEL

# ---------- 1. PROFILE & INTERESTS ----------

class Interest(models.Model):
    name = models.CharField(max_length=100, unique=True)
    def __str__(self):
        return self.name
    

# -------------------------------
# SUBSCRIPTION MODELS
# -------------------------------

class SubscriptionPlan(models.Model):
    """
    Plans available for users (Free / Premium / other)
    """
    PLAN_CHOICES = [
        ('free', 'Free'),
        ('premium', 'Premium'),
    ]

    name = models.CharField(max_length=100)
    plan_type = models.CharField(max_length=10, choices=PLAN_CHOICES, default='free')
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    duration_days = models.PositiveIntegerField(help_text="Duration in days")
    swipe_limit = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Daily swipe limit. Null = unlimited"
    )
    features = models.JSONField(default=list, blank=True, help_text="List of features")

    def __str__(self):
        return f"{self.name} ({self.plan_type})"


class UserSubscription(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="subscription")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(null=True, blank=True)  # <-- FIX HERE
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        """Auto-set end_date based on plan duration if not provided but plan exists"""
        if self.plan and not self.end_date:
            self.end_date = timezone.now() + timedelta(days=self.plan.duration_days)
        super().save(*args, **kwargs)

    def remaining_days(self):
        return max((self.end_date - timezone.now()).days, 0)

    def __str__(self):
        return f"{self.user.email} - {self.plan.name}"


class Transaction(models.Model):
    """
    Store payment or upgrade transactions for subscriptions
    """
    STATUS_CHOICES = [
        ("created", "Created"),
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
        ("cancelled", "Cancelled"),
    ]

    PAYMENT_TYPE_CHOICES = [
        ("subscription", "Subscription"),
        ("one_time", "One-time"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="transactions")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True, blank=True)

    # High-level classification of what this transaction represents
    payment_type = models.CharField(
        max_length=20,
        choices=PAYMENT_TYPE_CHOICES,
        default="subscription",
        help_text="Whether this is a subscription purchase or a one-time payment.",
    )

    # Monetary details
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default="INR")

    # Razorpay-specific identifiers
    razorpay_order_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    razorpay_payment_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    razorpay_signature = models.CharField(max_length=255, blank=True, null=True)

    # Gateway-side status and metadata
    gateway_status = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Raw status value from the payment gateway (e.g. captured, failed).",
    )

    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default="created")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        plan_name = self.plan.name if self.plan else "No plan"
        return f"{self.user.email} - {plan_name} - {self.status}"


class ChatBackground(models.Model):
    name = models.CharField(max_length=100)
    image = models.ImageField(upload_to="chat_backgrounds/")
    
    def __str__(self):
        return self.name