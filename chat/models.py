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
    # Use string reference to avoid direct import
    participants = models.ManyToManyField(CustomUser, related_name="chat_rooms")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        participants = ", ".join([p.email for p in self.participants.all()])
        return f"ChatRoom ({participants})"

class Message(models.Model):
    room = models.ForeignKey('ChatRoom', on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    content_encrypted = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to="chat_images/", blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    is_seen = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)  # ✅ new field

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
        return f"Message from {self.sender.email} at {self.timestamp}"