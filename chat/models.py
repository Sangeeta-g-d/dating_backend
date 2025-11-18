from django.db import models
from django.utils import timezone
from cryptography.fernet import Fernet
import base64
from auth_api.models import CustomUser
# Don't access settings.AUTH_USER_MODEL at module level
# We'll handle this in the model definition

# ---------- Encryption Utilities ----------
def encrypt_text(text: str) -> str:
    """
    Encrypts plain text using Fernet and returns a base64 encoded string.
    """
    from django.conf import settings  # Import inside function
    
    key = settings.FIELD_ENCRYPTION_KEY
    if isinstance(key, str):
        key = key.encode()
    
    fernet = Fernet(key)
    encrypted_data = fernet.encrypt(text.encode())
    return base64.urlsafe_b64encode(encrypted_data).decode()

def decrypt_text(encrypted: str) -> str:
    """
    Decrypts an encrypted string and returns plain text.
    """
    from django.conf import settings  # Import inside function
    
    key = settings.FIELD_ENCRYPTION_KEY
    if isinstance(key, str):
        key = key.encode()
    
    fernet = Fernet(key)
    try:
        encrypted_data = base64.urlsafe_b64decode(encrypted.encode())
        decrypted_data = fernet.decrypt(encrypted_data)
        return decrypted_data.decode()
    except Exception as e:
        raise ValueError(f"Decryption failed: {str(e)}")


# ---------- Models ----------
class ChatRoom(models.Model):
    """
    Strictly one-to-one conversation between two users.
    We keep both foreign keys to make querying by participant fast and to
    guarantee uniqueness.
    """
    user_a = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="chat_rooms_as_user_a",
    )
    user_b = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="chat_rooms_as_user_b",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_message_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ("-last_message_at", "-updated_at")
        constraints = [
            models.CheckConstraint(
                check=~models.Q(user_a=models.F("user_b")),
                name="chatroom_distinct_participants",
            ),
            models.UniqueConstraint(
                fields=("user_a", "user_b"),
                name="chatroom_unique_pair",
            ),
        ]

    def save(self, *args, **kwargs):
        """
        Always persist the smallest user id in user_a, so the unique constraint
        above prevents duplicate rooms for the same pair regardless of order.
        """
        if self.user_a_id and self.user_b_id and self.user_a_id > self.user_b_id:
            self.user_a_id, self.user_b_id = self.user_b_id, self.user_a_id
        super().save(*args, **kwargs)

    def participants(self):
        return [self.user_a, self.user_b]

    def __str__(self):
        return f"ChatRoom ({self.user_a.email} ↔ {self.user_b.email})"


class Message(models.Model):
    """
    Encrypts text payloads and allows optional media attachments that the
    websocket layer can deliver to clients in real time.
    """
    MEDIA_IMAGE = "image"
    MEDIA_VIDEO = "video"
    MEDIA_TYPE_CHOICES = (
        (MEDIA_IMAGE, "Image"),
        (MEDIA_VIDEO, "Video"),
    )

    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="sent_messages")
    content_encrypted = models.TextField(blank=True, null=True)
    media = models.FileField(upload_to="chat_media/", blank=True, null=True)
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPE_CHOICES, blank=True)
    reply_to = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replies",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    delivered_at = models.DateTimeField(blank=True, null=True)
    is_deleted = models.BooleanField(default=False)
    is_system = models.BooleanField(default=False)

    class Meta:
        ordering = ("created_at",)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        ChatRoom.objects.filter(id=self.room_id).update(last_message_at=self.created_at)

    @property
    def content(self):
        if self.is_deleted:
            return "This message was deleted"
        if self.content_encrypted:
            return decrypt_text(self.content_encrypted)
        return ""

    @content.setter
    def content(self, value):
        if value:
            self.content_encrypted = encrypt_text(value)
        else:
            self.content_encrypted = None

    def __str__(self):
        return f"Message from {self.sender.email} at {self.created_at}"


class MessageReceipt(models.Model):
    """
    Tracks delivery/seen state per participant, enabling read receipts and
    reliable push notifications.
    """
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="receipts")
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="message_receipts")
    delivered_at = models.DateTimeField(blank=True, null=True)
    seen_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        unique_together = ("message", "user")

    def mark_delivered(self):
        if not self.delivered_at:
            self.delivered_at = timezone.now()
            self.save(update_fields=["delivered_at"])

    def mark_seen(self):
        now = timezone.now()
        update_fields = []
        if not self.delivered_at:
            self.delivered_at = now
            update_fields.append("delivered_at")
        if not self.seen_at:
            self.seen_at = now
            update_fields.append("seen_at")
        if update_fields:
            self.save(update_fields=update_fields)

    def __str__(self):
        return f"Receipt for {self.user.email} on message {self.message_id}"

