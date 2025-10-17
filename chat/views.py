from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.pagination import PageNumberPagination
from .models import ChatRoom, Message
from .serializers import MessageSerializer
from auth_api.models import CustomUser


class MessagePagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class GetOrCreateChatRoomView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        sender = request.user
        receiver_id = request.data.get("receiver_id")

        if not receiver_id:
            return Response(
                {"status": 400, "message": "receiver_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            receiver = CustomUser.objects.get(id=receiver_id)
        except CustomUser.DoesNotExist:
            return Response(
                {"status": 404, "message": "Receiver not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # find or create room
        room = ChatRoom.objects.filter(participants=sender).filter(participants=receiver).first()
        created_new = False

        if not room:
            room = ChatRoom.objects.create()
            room.participants.add(sender, receiver)
            created_new = True

        # pagination
        paginator = MessagePagination()
        messages_qs = Message.objects.filter(room=room).order_by('-timestamp')
        paginated = paginator.paginate_queryset(messages_qs, request)

        serializer = MessageSerializer(paginated, many=True, context={'request': request})
        messages_data = serializer.data[::-1]  # chronological order

        data = {
            "id": room.id,
            "participants": [
                {"id": u.id, "email": u.email, "full_name": u.full_name}
                for u in room.participants.all()
            ],
            "messages": messages_data,
            "page": paginator.page.number,
            "total_pages": paginator.page.paginator.num_pages,
        }

        return Response(
            {
                "status": 200,
                "message": "New chat room created" if created_new else "Chat room fetched successfully",
                "data": data,
            },
            status=status.HTTP_200_OK,
        )
