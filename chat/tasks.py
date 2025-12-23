from celery import shared_task
from django.utils import timezone
from .models import AudioCall
from notifications.utils import create_notification


@shared_task(bind=True, max_retries=3)
def expire_audio_call(self, call_id):
    try:
        call = AudioCall.objects.get(id=call_id)
    except AudioCall.DoesNotExist:
        return

    # Only expire if still ringing
    if call.status != "ringing":
        return

    call.status = "missed"
    call.ended_at = timezone.now()
    call.save()

    # Notify caller
    create_notification(
        receiver=call.caller,
        sender=call.receiver,
        notif_type="missed_call",
        message="Missed audio call",
        extra_data={
            "call_id": str(call.id),
            "call_type": "audio"
        }
    )
