# notifications/utils.py

from notifications.models import Notification

def create_notification(receiver, sender, notif_type, message="", extra_data=None):
    if receiver == sender:
        return None  # Don't notify yourself

    return Notification.objects.create(
        user=receiver,        # receiver of the notification
        sender=sender,        # who triggered the notification
        type=notif_type,      # e.g. "like"
        message=message,
        extra_data=extra_data or {}
    )
