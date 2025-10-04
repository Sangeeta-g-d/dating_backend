from django.db import models
from django.conf import settings
from django.utils import timezone

# Create your models here.

User = settings.AUTH_USER_MODEL

# -------------------------------
# SWIPE & MATCH MODELS
# -------------------------------

class Swipe(models.Model):
    """
    Represents a user's swipe (like/dislike)
    """
    from_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="swipes_sent")
    to_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="swipes_received")
    is_liked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('from_user', 'to_user')


class MatchRequest(models.Model):
    """
    Represents a pending match request. Only after accepted, a Match is created.
    """
    from_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="match_requests_sent")
    to_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="match_requests_received")
    is_accepted = models.BooleanField(default=False)
    is_rejected = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        unique_together = ('from_user', 'to_user')

    def accept(self):
        """Call this method when the user accepts the match request"""
        self.is_accepted = True
        self.responded_at = timezone.now()
        self.save()
        # Create a Match record
        Match.create_match(self.from_user, self.to_user)


class Match(models.Model):
    """
    Created only when both users like each other and one accepted the request
    """
    user1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name="matches_as_user1")
    user2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name="matches_as_user2")
    matched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user1', 'user2')

    @staticmethod
    def create_match(user_a, user_b):
        """Creates a Match object with ordered users to avoid duplicates"""
        # Ensure consistent order
        user1, user2 = sorted([user_a, user_b], key=lambda x: x.id)
        match, created = Match.objects.get_or_create(user1=user1, user2=user2)
        return match

