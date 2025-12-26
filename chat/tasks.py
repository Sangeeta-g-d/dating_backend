# tasks.py
from celery import shared_task
from django.utils import timezone
from django.conf import settings
from .models import AudioCall
from notifications.utils import create_notification


@shared_task(bind=True, max_retries=3)
def expire_call(self, call_id):
    """
    Expire a call if it's still ringing after timeout
    Works for both audio and video calls
    """
    try:
        call = AudioCall.objects.get(id=call_id)
    except AudioCall.DoesNotExist:
        return

    # Only expire if still ringing
    if call.status != "ringing":
        return

    print(f"⏰ Auto-expiring {call.call_type} call: {call.id}")

    call.status = "missed"
    call.ended_at = timezone.now()
    call.save()

    # Notify caller
    create_notification(
        receiver=call.caller,
        sender=call.receiver,
        notif_type="missed_call",
        message=f"Missed {call.call_type} call",
        extra_data={
            "call_id": str(call.id),
            "call_type": call.call_type,
            "timestamp": timezone.now().isoformat()
        }
    )


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
