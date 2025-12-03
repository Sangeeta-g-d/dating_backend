from firebase_admin import messaging
from notifications.models import Notification
from notifications.firebase_init import *
from auth_api.models import DeviceToken

def send_push_notification(device_tokens, title, body, data=None):
    if not device_tokens:
        return

    message = messaging.MulticastMessage(
        notification=messaging.Notification(title=title, body=body),
        data=data or {},
        tokens=device_tokens
    )

    response = messaging.send_multicast(message)
    print(f"[FCM] Sent: {response.success_count}, Failed: {response.failure_count}")
    return response


def create_notification(receiver, sender, notif_type, message="", extra_data=None):
    if receiver == sender:
        return None

    # Save database notification
    notification = Notification.objects.create(
        user=receiver,
        sender=sender,
        type=notif_type,
        message=message,
        extra_data=extra_data or {}
    )

    # Fetch FCM tokens from DeviceToken table
    device_tokens = list(
        receiver.device_tokens.values_list("fcm_token", flat=True)
    )

    # Send FCM push
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
