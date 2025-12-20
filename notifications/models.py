from django.db import models
from auth_api.models import CustomUser


class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ("profile_view", "Profile View"),
        ("new_match", "New Match"),
        ("new_message", "New Message"),
        ("story_view", "Story View"),
        ("like", "Post Like"),
        ("comment", "Post Comment"),
        ("system", "System Notification"),
        ("incoming_call", "Incoming Call"),   # ✅ ADD
        ("missed_call", "Missed Call"),        # optional
        ("call_ended", "Call Ended"), 
    ]

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="notifications"
    )  # receiver

    sender = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications_sent"
    )  # who triggered it

    type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    message = models.TextField(blank=True, null=True)

    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    # For feature-related payload (e.g., post id, story id)
    extra_data = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.user.email} - {self.type}"



class ProfileView(models.Model):
    viewer = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="profiles_viewed"
    )
    viewed_user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="profile_views"
    )
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('viewer', 'viewed_user')

    def __str__(self):
        return f"{self.viewer.email} viewed {self.viewed_user.email}"
