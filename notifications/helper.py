from django.utils import timezone
from .models import ProfileView, Notification, CustomUser


def handle_profile_view(viewer, viewed_user):
    if viewer == viewed_user:
        return  # ignore self views

    # Save or update profile view record
    ProfileView.objects.update_or_create(
        viewer=viewer,
        viewed_user=viewed_user,
        defaults={"viewed_at": timezone.now()}
    )

    # Check subscription
    subscription = getattr(viewed_user, "subscription", None)
    can_reveal = (
        subscription 
        and subscription.plan 
        and subscription.plan.plan_type == "premium"
    )

    # Notification content
    if can_reveal:
        message = f"{viewer.full_name} viewed your profile"
        sender_obj = viewer
        extra = {"viewer_id": viewer.id}
    else:
        message = "Someone viewed your profile"
        sender_obj = None
        extra = {}

    # Save notification
    Notification.objects.create(
        user=viewed_user,
        sender=sender_obj,
        type="profile_view",
        message=message,
        extra_data=extra
    )
