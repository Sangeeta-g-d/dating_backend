# notifications/firebase_helper.py
from firebase_admin import messaging
from notifications.models import Notification
from notifications.firebase_init import initialize_firebase


def send_push_notification(device_tokens, title, body, data=None):
    print("\n📡 [DEBUG] send_push_notification() called")
    print(f"📡 [DEBUG] Device Tokens: {device_tokens}")
    print(f"📡 [DEBUG] Title: {title}")
    print(f"📡 [DEBUG] Body: {body}")
    print(f"📡 [DEBUG] Data: {data}")

    if not device_tokens:
        print("⚠️ [DEBUG] No device tokens found. Skipping FCM.")
        return

    # Ensure Firebase is initialized
    if not initialize_firebase():
        print("❌ [FCM ERROR] Firebase not initialized. Cannot send notification.")
        return None

    print("🚀 [DEBUG] Sending FCM messages...")

    try:
        # Try send_multicast first (Firebase Admin SDK 4.4.0+)
        if hasattr(messaging, 'send_multicast'):
            message = messaging.MulticastMessage(
                notification=messaging.Notification(title=title, body=body),
                data=data or {},
                tokens=device_tokens
            )
            response = messaging.send_multicast(message)
        elif hasattr(messaging, 'send_each'):
            # Fallback for older versions
            print("⚠️ [DEBUG] Using send_each method (older SDK)")
            messages = [
                messaging.Message(
                    notification=messaging.Notification(title=title, body=body),
                    data=data or {},
                    token=token
                )
                for token in device_tokens
            ]
            response = messaging.send_each(messages)
        else:
            # Last resort: send one by one
            print("⚠️ [DEBUG] Using individual send method")
            success_count = 0
            failure_count = 0
            for token in device_tokens:
                try:
                    message = messaging.Message(
                        notification=messaging.Notification(title=title, body=body),
                        data=data or {},
                        token=token
                    )
                    messaging.send(message)
                    success_count += 1
                except Exception as e:
                    print(f"❌ [FCM ERROR] Failed to send to token {token}: {str(e)}")
                    failure_count += 1
            
            # Create a response-like object
            class Response:
                def __init__(self, success, failure):
                    self.success_count = success
                    self.failure_count = failure
            
            response = Response(success_count, failure_count)
        
        print(f"✅ [FCM DEBUG] Success: {response.success_count}, Failed: {response.failure_count}")
        
        # Log any failures if response has detailed info
        if hasattr(response, 'responses') and response.failure_count > 0:
            for idx, resp in enumerate(response.responses):
                if not resp.success:
                    print(f"❌ [FCM ERROR] Token {device_tokens[idx]}: {resp.exception}")
        
        return response
    except Exception as e:
        print(f"❌ [FCM ERROR] {str(e)}")
        import traceback
        print(f"❌ [TRACEBACK] {traceback.format_exc()}")
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