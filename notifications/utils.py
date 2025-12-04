import os
import firebase_admin
from firebase_admin import credentials, messaging

print("🔧 [DEBUG] Loading Firebase configuration...")

BASE_DIR = os.path.dirname(__file__)
FIREBASE_CRED_PATH = os.path.join(BASE_DIR, "firebase.json")
print(f"🔧 [DEBUG] Firebase JSON Path: {FIREBASE_CRED_PATH}")

if not firebase_admin._apps:
    print("🚀 [DEBUG] Initializing Firebase app...")
    cred = credentials.Certificate(FIREBASE_CRED_PATH)
    firebase_admin.initialize_app(cred)
    print("✅ [DEBUG] Firebase initialized successfully!")
else:
    print("⚠️ [DEBUG] Firebase app already initialized.")


from firebase_admin import messaging
from notifications.models import Notification
from notifications.firebase_init import *
from auth_api.models import DeviceToken


def send_push_notification(device_tokens, title, body, data=None):
    print("\n📡 [DEBUG] send_push_notification() called")
    print(f"📡 [DEBUG] Device Tokens: {device_tokens}")
    print(f"📡 [DEBUG] Title: {title}")
    print(f"📡 [DEBUG] Body: {body}")
    print(f"📡 [DEBUG] Data: {data}")

    if not device_tokens:
        print("⚠️ [DEBUG] No device tokens found. Skipping FCM.")
        return

    message = messaging.MulticastMessage(
        notification=messaging.Notification(title=title, body=body),
        data=data or {},
        tokens=device_tokens
    )

    print("🚀 [DEBUG] Sending FCM multicast message...")

    try:
        response = messaging.send_multicast(message)
        print(f"✅ [FCM DEBUG] Success: {response.success_count}, Failed: {response.failure_count}")
        return response
    except Exception as e:
        print(f"❌ [FCM ERROR] {str(e)}")
        return None


def create_notification(receiver, sender, notif_type, message="", extra_data=None):
    print("\n🔔 [DEBUG] create_notification() called")
    print(f"🔔 [DEBUG] Receiver: {receiver.id}, Sender: {sender.id if sender else 'None'}")
    print(f"🔔 [DEBUG] Notification Type: {notif_type}")
    print(f"🔔 [DEBUG] Message: {message}")

    if receiver == sender:
        print("⚠️ [DEBUG] Receiver and sender are the same. Skipping notification.")
        return None

    # Save DB notification
    print("🗄️ [DEBUG] Saving notification in database...")
    notification = Notification.objects.create(
        user=receiver,
        sender=sender,
        type=notif_type,
        message=message,
        extra_data=extra_data or {}
    )
    print(f"✅ [DEBUG] Notification saved with ID: {notification.id}")

    # Fetch device tokens
    print("🔍 [DEBUG] Fetching device tokens for receiver...")
    device_tokens = list(
        receiver.device_tokens.values_list("fcm_token", flat=True)
    )
    print(f"🔍 [DEBUG] Fetched Tokens: {device_tokens}")

    # Send Firebase Notification
    if device_tokens:
        print("📨 [DEBUG] Sending push notification...")
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
    else:
        print("⚠️ [DEBUG] No device tokens found for this user.")

    print("🏁 [DEBUG] create_notification() completed.")
    return notification
