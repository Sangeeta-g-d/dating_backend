from firebase_admin import messaging
from notifications.models import Notification
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

    # Create messages for each token
    messages = [
        messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data=data or {},
            token=token
        )
        for token in device_tokens
    ]

    print("🚀 [DEBUG] Sending FCM messages...")

    try:
        # Use send_each_for_multicast or send_each (both work)
        if hasattr(messaging, 'send_each_for_multicast'):
            # Newer versions
            response = messaging.send_each_for_multicast(
                messaging.MulticastMessage(
                    notification=messaging.Notification(title=title, body=body),
                    data=data or {},
                    tokens=device_tokens
                )
            )
        elif hasattr(messaging, 'send_multicast'):
            # Version 4.4.0+
            response = messaging.send_multicast(
                messaging.MulticastMessage(
                    notification=messaging.Notification(title=title, body=body),
                    data=data or {},
                    tokens=device_tokens
                )
            )
        else:
            # Fallback: send individually
            print("⚠️ [DEBUG] Using individual send method (older SDK)")
            response = messaging.send_each(messages)
        
        print(f"✅ [FCM DEBUG] Success: {response.success_count}, Failed: {response.failure_count}")
        
        # Log any failures
        if response.failure_count > 0:
            for idx, resp in enumerate(response.responses):
                if not resp.success:
                    print(f"❌ [FCM ERROR] Token {device_tokens[idx]}: {resp.exception}")
        
        return response
    except AttributeError as e:
        print(f"❌ [FCM ERROR] Method not available: {str(e)}")
        print("💡 [HINT] Try upgrading firebase-admin: pip install --upgrade firebase-admin")
        return None
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