from django.shortcuts import render
from .models import Notification, ProfileView
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
# Create your views here.


class NotificationListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        # Fetch all notifications, newest first
        notifications = Notification.objects.filter(user=user).order_by("-created_at")

        # Build response list
        notification_list = []
        base_url = request.build_absolute_uri("/")[:-1]

        for notif in notifications:
            notification_list.append({
                "id": notif.id,
                "type": notif.type,
                "message": notif.message,
                "is_read": notif.is_read,
                "created_at": notif.created_at,
                "sender": {
                    "id": notif.sender.id if notif.sender else None,
                    "full_name": notif.sender.full_name if notif.sender else None,
                    "profile_image": (
                        f"{base_url}{notif.sender.profile_photo.url}"
                        if notif.sender and notif.sender.profile_photo else None
                    )
                },
                "extra_data": notif.extra_data or {}
            })

        response_data = {
            "status": "200",
            "message": "Notifications fetched successfully.",
            "Response": notification_list,
        }

        return Response(response_data, status=status.HTTP_200_OK)


class MarkAsReadAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        notification_ids = request.data.get("notification_ids")

        # Validate input
        if not notification_ids or not isinstance(notification_ids, list):
            return Response({
                "status": "400",
                "message": "notification_ids must be a list of IDs.",
                "Response": []
            }, status=status.HTTP_400_BAD_REQUEST)

        user = request.user

        # Filter only notifications belonging to the user
        notifications = Notification.objects.filter(
            id__in=notification_ids,
            user=user,
            is_read=False
        )

        updated_count = notifications.update(is_read=True)

        response_data = {
            "status": "200",
            "message": f"{updated_count} notification(s) marked as read.",
            "Response": {
                "updated_count": updated_count,
                "notification_ids": notification_ids
            }
        }

        return Response(response_data, status=status.HTTP_200_OK)
