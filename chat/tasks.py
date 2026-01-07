# tasks.py
from celery import shared_task
from django.utils import timezone
from django.conf import settings
from .models import AudioCall
from notifications.utils import create_notification
from notifications.utils import send_push_notification


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



@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=5, retry_kwargs={"max_retries": 3})
def send_message_notification_task(room_id, sender_id, message_id, message_text):
    from chat.models import ChatRoom, Message

    message = Message.objects.get(id=message_id)
    room = ChatRoom.objects.get(id=room_id)

    recipient = room.user_b if room.user_a_id == sender_id else room.user_a
    if recipient.id == sender_id:
        return

    tokens = list(recipient.device_tokens.values_list("fcm_token", flat=True))
    if not tokens:
        return

    send_push_notification(
        device_tokens=tokens,
        title="",
        body=message_text[:50],
        data={
            "room_id": str(room_id),
            "message_id": str(message_id),
            "type": "new_message",
        }
    )