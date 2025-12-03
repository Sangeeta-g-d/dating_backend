from notifications.models import Notification
from firebase_admin import messaging
from notifications.firebase_init import *

def send_push_notification(device_tokens, title, body, data=None):
    """
    Sends push notification using Firebase FCM.
    device_tokens: list of FCM tokens
    """

    if not device_tokens:
        return

    message = messaging.MulticastMessage(
        notification=messaging.Notification(
            title=title,
            body=body
        ),
        data=data or {},
        tokens=device_tokens
    )

    response = messaging.send_multicast(message)
    print(f"[FCM] Successfully sent: {response.success_count}, Failed: {response.failure_count}")
    return response


def create_notification(receiver, sender, notif_type, message="", extra_data=None):
    if receiver == sender:
        return None  # Don't notify yourself

    # 1️⃣ Save notification in database
    notification = Notification.objects.create(
        user=receiver,
        sender=sender,
        type=notif_type,
        message=message,
        extra_data=extra_data or {}
    )

    # 2️⃣ Fetch FCM tokens from receiver model
    # Assuming your User model has: device_tokens = JSON field OR related table
    device_tokens = []

    if hasattr(receiver, "device_tokens"):
        if isinstance(receiver.device_tokens, list):
            device_tokens = receiver.device_tokens
        else:
            device_tokens = [receiver.device_tokens]

    # 3️⃣ Send Firebase Push Notification
    if device_tokens:
        send_push_notification(
            device_tokens=device_tokens,
            title=f"New {notif_type}",
            body=message,
            data={
                "notification_id": str(notification.id),
                "type": notif_type,
                "sender_id": str(sender.id) if sender else "",
            }
        )

    return notification
