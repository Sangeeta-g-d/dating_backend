from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.utils import timezone

from .models import ChatRoom, MessageReceipt
from dating_backend.timezone_utils import format_to_ist


class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.room_id = int(self.scope["url_route"]["kwargs"]["room_id"])
        self.group_name = f"chat_{self.room_id}"
        user = self.scope["user"]

        if user.is_anonymous or not await self._user_belongs_to_room(user.id):
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        action = content.get("action")
        user = self.scope["user"]

        if action == "typing":
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "chat.typing",
                    "payload": {
                        "user_id": user.id,
                        "is_typing": bool(content.get("is_typing")),
                    },
                },
            )
        elif action == "seen":
            message_ids = content.get("message_ids") or []
            payload = await self._mark_messages_seen(user.id, message_ids)
            if payload:
                await self.channel_layer.group_send(
                    self.group_name,
                    {"type": "chat.receipt", "payload": payload},
                )
        elif action == "ping":
            await self.send_json({"event": "pong"})

    async def chat_message(self, event):
        await self.send_json({"event": "message", "data": event["payload"]})

    async def chat_receipt(self, event):
        await self.send_json({"event": "receipt", "data": event["payload"]})

    async def chat_typing(self, event):
        await self.send_json({"event": "typing", "data": event["payload"]})

    @database_sync_to_async
    def _user_belongs_to_room(self, user_id):
        try:
            room = ChatRoom.objects.only("user_a_id", "user_b_id").get(id=self.room_id)
        except ChatRoom.DoesNotExist:
            return False
        return user_id in (room.user_a_id, room.user_b_id)

    @database_sync_to_async
    def _mark_messages_seen(self, user_id, message_ids):
        qs = MessageReceipt.objects.filter(
            message__room_id=self.room_id,
            user_id=user_id,
            seen_at__isnull=True,
        )
        if message_ids:
            qs = qs.filter(message_id__in=message_ids)

        now = timezone.now()
        updated_ids = []
        for receipt in qs:
            receipt.delivered_at = receipt.delivered_at or now
            receipt.seen_at = now
            receipt.save(update_fields=["delivered_at", "seen_at"])
            updated_ids.append(receipt.message_id)

        if not updated_ids:
            return None

        return {"message_ids": updated_ids, "seen_at": format_to_ist(now), "user_id": user_id}

