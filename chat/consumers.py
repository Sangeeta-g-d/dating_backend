import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
import logging

logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.room_id = self.scope["url_route"]["kwargs"]["room_id"]
        self.room_group_name = f"chat_{self.room_id}"
        self.user = self.scope["user"]

        logger.info(f"WebSocket connection attempt - Room: {self.room_id}, User: {self.user}")

        if isinstance(self.user, AnonymousUser) or not self.user.is_authenticated:
            logger.warning(f"Authentication failed - User is anonymous or not authenticated")
            await self.close(code=4001)  # Custom close code for authentication failure
            return
        
        if not await self.has_room_access():
            logger.warning(f"Room access denied - User {self.user.id} cannot access room {self.room_id}")
            await self.close(code=4003)  # Custom close code for room access denied
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        logger.info(f"WebSocket connection accepted - User {self.user.id} in room {self.room_id}")

    async def disconnect(self, close_code):
        logger.info(f"WebSocket disconnected - Code: {close_code}")
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        msg_type = data.get("type")

        # ----------------- TYPING INDICATOR -----------------
        if msg_type == "typing":
            is_typing = data.get("is_typing", False)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "typing_event",
                    "user_id": self.user.id,
                    "user_name": getattr(self.user, 'full_name', ''),
                    "is_typing": is_typing,
                }
            )
            return

        # ----------------- SEND MESSAGE -----------------
        if msg_type == "message":
            message_text = data.get("message")
            msg_obj = await self.save_message(message_text)
            await self.create_receipts(msg_obj)

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "chat_message",
                    "event": "new_message",
                    "message_id": msg_obj.id,
                    "message": msg_obj.content,
                    "sender_id": self.user.id,
                    "sender_name": getattr(self.user, 'full_name', ''),
                    "timestamp": msg_obj.created_at.isoformat(),
                }
            )
            return

        # ----------------- MARK SEEN -----------------
        if msg_type == "seen":
            msg_id = data.get("message_id")
            if msg_id:
                receipt = await self.mark_as_seen(msg_id)
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "seen_event",
                        "message_id": msg_id,
                        "user_id": self.user.id,
                        "user_name": getattr(self.user, 'full_name', ''),
                        "seen_at": receipt.seen_at.isoformat(),
                    }
                )
            return

    # ======================================================
    #                   EVENT HANDLERS
    # ======================================================

    async def typing_event(self, event):
        await self.send(text_data=json.dumps({
            "event": "typing",
            "user_id": event["user_id"],
            "user_name": event.get("user_name", ""),
            "is_typing": event["is_typing"],
        }))

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))

    async def seen_event(self, event):
        await self.send(text_data=json.dumps(event))


    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            "type": "media_message",
            "data": event["message"]
        }))

    async def chat_delete(self, event):
        await self.send(text_data=json.dumps(event["data"]))

    # ======================================================
    #                   DATABASE HELPERS
    # ======================================================

    @database_sync_to_async
    def has_room_access(self):
        from chat.models import ChatRoom
        try:
            room = ChatRoom.objects.get(id=self.room_id)
            has_access = self.user in [room.user_a, room.user_b]
            logger.info(f"Room access check - Room {self.room_id}, User {self.user.id}, Access: {has_access}")
            return has_access
        except ChatRoom.DoesNotExist:
            logger.error(f"Room {self.room_id} does not exist")
            return False
        
    @database_sync_to_async
    def save_message(self, text):
        from chat.models import ChatRoom, Message

        room = ChatRoom.objects.get(id=self.room_id)
        return Message.objects.create(
            room=room,
            sender=self.user,
            content=text
        )

    @database_sync_to_async
    def create_receipts(self, message_obj):
        from chat.models import ChatRoom, MessageReceipt

        room = ChatRoom.objects.get(id=self.room_id)
        participants = room.participants()

        for user in participants:
            receipt, _ = MessageReceipt.objects.get_or_create(
                message=message_obj, user=user
            )
            if user.id == message_obj.sender_id:
                receipt.mark_delivered()

        return True

    @database_sync_to_async
    def mark_as_seen(self, message_id):
        from chat.models import MessageReceipt

        receipt = MessageReceipt.objects.get(message_id=message_id, user=self.user)
        receipt.mark_seen()
        return receipt