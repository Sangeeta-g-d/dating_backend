# tasks.py
from celery import shared_task
from django.utils import timezone
from django.conf import settings
from .models import AudioCall
from notifications.utils import create_notification
from notifications.utils import send_push_notification
from chat.models import ChatRoom
from auth_api.models import CustomUser
from notifications.utils import send_push_notification
import logging

@shared_task(bind=True, max_retries=3)
def expire_call(self, call_id):
    """
    Expire a call if it's still ringing after timeout
    Works for both audio and video calls
    """
    try:
        call = AudioCall.objects.get(id=call_id)
    except AudioCall.DoesNotExist:
        print(f"⚠️ Call {call_id} not found for expiration")
        return

    # Only expire if still ringing
    if call.status != "ringing":
        print(f"⏰ Call {call.id} already {call.status}, skipping expiration")
        return

    print(f"⏰ Auto-expiring {call.call_type} call: {call.id}")

    call.status = "missed"
    call.ended_at = timezone.now()
    call.save()

    # Notify caller (not receiver!) that call was missed
    try:
        create_notification(
            receiver=call.caller,  # Notify the person who MADE the call
            sender=call.receiver,   # From the person who DIDN'T answer
            notif_type=f"{call.call_type}_call_missed",  # More specific notification type
            message=f"{call.receiver.full_name} didn't answer",
            extra_data={
                "call_id": str(call.id),
                "call_type": call.call_type,
                "receiver_id": str(call.receiver.id),
                "receiver_name": call.receiver.full_name,
                "timestamp": timezone.now().isoformat()
            }
        )
    except Exception as e:
        print(f"⚠️ Failed to send missed call notification: {e}")

@shared_task
def cleanup_old_calls():
    """Clean up old ended calls (older than 30 days)"""
    from django.utils import timezone
    from datetime import timedelta
    
    thirty_days_ago = timezone.now() - timedelta(days=30)
    
    old_calls = AudioCall.objects.filter(
        ended_at__lt=thirty_days_ago
    )
    
    count = old_calls.count()
    old_calls.delete()
    
    print(f"🧹 Cleaned up {count} old calls")


@shared_task
def force_end_call(call_id):
    from django.utils import timezone
    from chat.models import AudioCall

    try:
        call = AudioCall.objects.get(id=call_id, status="accepted")
        call.status = "ended"
        call.ended_at = timezone.now()
        call.save()
    except AudioCall.DoesNotExist:
        pass



@shared_task(autoretry_for=(Exception,), retry_backoff=5, retry_kwargs={"max_retries": 3})
def send_message_notification_task(room_id, sender_id, message_id, message_text):
    """
    Send push notification for new message.
    message_text is passed directly to avoid decryption issues in Celery.
    """

    
    logger = logging.getLogger(__name__)
    
    try:
        # Get room and participants
        room = ChatRoom.objects.select_related('user_a', 'user_b').get(id=room_id)
        sender = CustomUser.objects.only('id', 'full_name').get(id=sender_id)
        
        # Determine recipient (the other person in the chat)
        recipient = room.user_b if room.user_a_id == sender_id else room.user_a
        
        # Skip if recipient is somehow the sender
        if recipient.id == sender_id:
            logger.debug("Recipient is sender, skipping notification")
            return
        
        # Get device tokens
        tokens = list(recipient.device_tokens.values_list("fcm_token", flat=True))
        if not tokens:
            logger.debug(f"No device tokens for user {recipient.id}")
            return
        
        # Format notification
        sender_name = getattr(sender, 'full_name', 'Someone')
        preview = message_text[:50] + "..." if len(message_text) > 50 else message_text
        
        # Send push notification
        send_push_notification(
            device_tokens=tokens,
            title="",
            body=f"{sender_name}: {preview}",
            data={
                "room_id": str(room_id),
                "message_id": str(message_id),
                "sender_id": str(sender_id),
                "sender_name": sender_name,
                "type": "new_message",
            }
        )
        
        logger.info(f"✅ Push notification sent to user {recipient.id} for message {message_id}")
        
    except ChatRoom.DoesNotExist:
        logger.error(f"ChatRoom {room_id} not found")
    except CustomUser.DoesNotExist:
        logger.error(f"Sender {sender_id} not found")
    except Exception as e:
        logger.error(f"❌ Error sending message notification: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise  # Re-raise to trigger Celery retry