from django.shortcuts import render
from .models import Notification, ProfileView
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from chat.pagination import StandardSearchPagination


# Create your views here.

class NotificationListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user

            notifications = Notification.objects.filter(user=user).order_by("-created_at")

            paginator = StandardSearchPagination()

            try:
                paginated_notifications = paginator.paginate_queryset(notifications, request)
            except NotFound:
                page_num = request.query_params.get('page', 1)
                try:
                    page_num = int(page_num)
                except (ValueError, TypeError):
                    page_num = 1

                total_items = notifications.count()
                page_size = paginator.page_size
                total_pages = (total_items + page_size - 1) // page_size

                return Response({
                    "status": "200",
                    "message": "Notifications fetched successfully.",
                    "Response": [],
                    "pagination": {
                        "current_page": page_num,
                        "page_size": page_size,
                        "total_items": total_items,
                        "total_pages": total_pages,
                        "has_next_page": False,
                        "has_previous_page": page_num > 1
                    }
                }, status=status.HTTP_200_OK)

            base_url = request.build_absolute_uri("/")[:-1]

            notification_list = []
            for notif in paginated_notifications:
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

            # Pagination calculations
            page_num = request.query_params.get('page', 1)
            try:
                page_num = int(page_num)
            except (ValueError, TypeError):
                page_num = 1

            total_items = notifications.count()
            page_size = paginator.page_size
            total_pages = (total_items + page_size - 1) // page_size
            has_next_page = page_num < total_pages
            has_previous_page = page_num > 1

            response_data = {
                "status": "200",
                "message": "Notifications fetched successfully.",
                "Response": notification_list,
                "pagination": {
                    "current_page": page_num,
                    "page_size": page_size,
                    "total_items": total_items,
                    "total_pages": total_pages,
                    "has_next_page": has_next_page,
                    "has_previous_page": has_previous_page
                }
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "status": "500",
                "message": f"Error fetching notifications: {str(e)}",
                "Response": []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
