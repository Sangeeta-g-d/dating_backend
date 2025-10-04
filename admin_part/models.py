from django.db import models
from django.conf import settings

# Create your models here.

User = settings.AUTH_USER_MODEL

# ---------- 1. PROFILE & INTERESTS ----------

class Interest(models.Model):
    name = models.CharField(max_length=100, unique=True)
    icon = models.CharField(max_length=100, blank=True, null=True)  # optional UI icon

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
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.plan_type})"


class UserSubscription(models.Model):
    """
    Tracks a user's active subscription
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="subscription")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        """Auto-set end_date based on plan duration if not provided"""
        if not self.end_date and self.plan:
            self.end_date = self.start_date + timedelta(days=self.plan.duration_days)
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
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed')
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="transactions")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True)
    payment_id = models.CharField(max_length=255, blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - {self.plan.name} - {self.status}"
