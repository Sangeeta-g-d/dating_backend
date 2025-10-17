import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f"chat_{self.room_name}"

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # Receive message from WebSocket
    async def receive(self, text_data):
        # Import inside method to avoid circular imports
        from django.contrib.auth import get_user_model
        from .models import ChatRoom, Message
        from django.conf import settings
        
        User = get_user_model()
        
        data = json.loads(text_data)
        message = data.get("message")
        sender_id = data.get("sender_id")

        sender = await sync_to_async(User.objects.get)(id=sender_id)
        room = await sync_to_async(ChatRoom.objects.get)(id=self.room_name)
        msg_obj = await sync_to_async(Message.objects.create)(room=room, sender=sender, content=message)

        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "message": message,
                "sender_id": sender_id,
                "timestamp": str(msg_obj.timestamp),
            }
        )

        # Send push notification via FCM
        await sync_to_async(self.send_push_notification)(room, sender, message)

    # Receive message from room group
    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))

    def send_push_notification(self, room, sender, message):
        # Import inside method to avoid circular imports
        from pyfcm import FCMNotification
        from django.conf import settings
        
        # Send notification to other participants
        push_service = FCMNotification(api_key=settings.FCM_SERVER_KEY)
        recipients = room.participants.exclude(id=sender.id)
        for user in recipients:
            if hasattr(user, 'fcm_token') and user.fcm_token:  # store FCM token in User model
                push_service.notify_single_device(
                    registration_id=user.fcm_token,
                    message_title=f"New message from {getattr(sender, 'full_name', sender.username)}",
                    message_body=message
                )