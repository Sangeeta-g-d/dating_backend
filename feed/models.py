from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
import json

User = settings.AUTH_USER_MODEL

# -------------------------
# Post Model
# -------------------------
def validate_media_length(value):
    if len(value) > 5:
        raise ValidationError("You can upload a maximum of 5 media files per post.")

class Post(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posts')
    caption = models.TextField(blank=True, null=True)
    # Store a list of media URLs (images or videos)
    media = models.JSONField(default=list, validators=[validate_media_length])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def total_likes(self):
        return self.likes.count()

    def total_comments(self):
        return self.comments.count()

    def __str__(self):
        return f"{self.user} - {self.caption[:20]}"

# -------------------------
# Comment Model
# -------------------------
class Comment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    content = models.TextField()
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, 
        related_name='replies', blank=True, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def is_reply(self):
        return self.parent is not None

    def __str__(self):
        if self.is_reply():
            return f"Reply by {self.user} to comment {self.parent.id}"
        return f"{self.user} - {self.content[:20]}"


# -------------------------
# Like Model
# -------------------------
class Like(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='likes')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'post')  # Prevent multiple likes from same user

    def __str__(self):
        return f"{self.user} liked {self.post.id}"
