from django.db import models
from django.conf import settings
from django.utils import timezone

# Create your models here.

User = settings.AUTH_USER_MODEL

# -------------------------------
# SWIPE & MATCH MODELS
# -------------------------------
class Swipe(models.Model):
    from_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="swipes_sent")
    to_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="swipes_received")
    is_liked = models.BooleanField(default=False)
    is_accepted = models.BooleanField(default=False)
    is_rejected = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        unique_together = ('from_user', 'to_user')

    def accept(self):
        """Mark swipe accepted and create a match"""
        self.is_accepted = True
        self.is_rejected = False
        self.responded_at = timezone.now()
        self.save()
        Match.create_match(self.from_user, self.to_user)

    def reject(self):
        """Mark swipe rejected"""
        self.is_rejected = True
        self.is_accepted = False
        self.responded_at = timezone.now()
        self.save()



class Match(models.Model):
    user1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name="matches_as_user1")
    user2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name="matches_as_user2")
    matched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user1', 'user2')

    @staticmethod
    def create_match(user_a, user_b):
        user1, user2 = sorted([user_a, user_b], key=lambda x: x.id)
        match, created = Match.objects.get_or_create(user1=user1, user2=user2)
        return match

    @staticmethod
    def get_user_matches(user):
        """Return all matched users for given user"""
        matches = Match.objects.filter(models.Q(user1=user) | models.Q(user2=user))
        matched_users = [m.user1 if m.user2 == user else m.user2 for m in matches]
        return matched_users
