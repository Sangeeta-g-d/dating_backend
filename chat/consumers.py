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
            await self.close(code=4001)
            return
        
        if not await self.has_room_access():
            logger.warning(f"Room access denied - User {self.user.id} cannot access room {self.room_id}")
            await self.close(code=4003)
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
            reply_to_id = data.get("reply_to")

            msg_obj = await self.save_message(message_text, reply_to_id)
            await self.create_receipts(msg_obj)

            # Send Firebase notification to the recipient
            await self.send_message_notification(msg_obj, message_text)

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "chat_message",
                    "event": "new_message",
                    "message_id": msg_obj.id,
                    "message": msg_obj.content,
                    "sender_id": self.user.id,
                    "sender_name": getattr(self.user, 'full_name', ''),
                    "reply_to": reply_to_id,
                    "timestamp": msg_obj.created_at.isoformat(),
                }
            )
            return

        # ----------------- MARK SEEN -----------------
        if msg_type == "seen":
            message_ids = data.get("message_ids", [])

            if isinstance(message_ids, int):  
                message_ids = [message_ids]

            seen_list = await self.mark_multiple_as_seen(message_ids)

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "seen_event",
                    "message_ids": message_ids,
                    "user_id": self.user.id,
                    "user_name": getattr(self.user, 'full_name', ''),
                    "seen_at": seen_list["timestamp"],
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

    async def media_message(self, event):
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
    def save_message(self, text, reply_to_id=None):
        from chat.models import ChatRoom, Message
    
        room = ChatRoom.objects.get(id=self.room_id)
    
        reply_obj = None
        if reply_to_id:
            try:
                reply_obj = Message.objects.get(id=reply_to_id, room=room)
            except Message.DoesNotExist:
                reply_obj = None
    
        msg = Message(
            room=room,
            sender=self.user,
            reply_to=reply_obj
        )
        msg.content = text  # encryption handled in setter
        msg.save()
        return msg

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
    def mark_multiple_as_seen(self, message_ids):
        from chat.models import MessageReceipt
        from django.utils import timezone
    
        timestamp = timezone.now()
    
        for mid in message_ids:
            try:
                receipt = MessageReceipt.objects.get(message_id=mid, user=self.user)
                receipt.seen_at = timestamp
                receipt.save()
            except MessageReceipt.DoesNotExist:
                pass
            
        return {"timestamp": timestamp.isoformat()}

    @database_sync_to_async
    def send_message_notification(self, message_obj, message_text):
        """
        Send Firebase notification to the recipient of the message
        """
        from chat.models import ChatRoom
        from notifications.utils import create_notification
        from auth_api.models import CustomUser
        
        try:
            room = ChatRoom.objects.get(id=self.room_id)
            
            # Determine the recipient (the other person in the chat)
            recipient = room.user_b if room.user_a.id == self.user.id else room.user_a
            
            # Don't send notification if recipient is the sender
            if recipient.id == self.user.id:
                logger.debug("Recipient is sender, skipping notification")
                return
            
            # Get sender's name
            sender_name = getattr(self.user, 'full_name', 'Someone')
            
            # Truncate message for notification (max 50 chars)
            preview = message_text[:50] + "..." if len(message_text) > 50 else message_text
            
            notification_message = f"{sender_name}: {preview}"
            
            # Create notification with extra data
            extra_data = {
                "room_id": str(self.room_id),
                "message_id": str(message_obj.id),
                "sender_name": sender_name,
            }
            
            logger.info(f"📨 Sending message notification to user {recipient.id}")
            
            # Use your existing create_notification function
            create_notification(
                receiver=recipient,
                sender=self.user,
                notif_type="new_message",
                message=notification_message,
                extra_data=extra_data
            )
            
            logger.info(f"✅ Message notification sent successfully")
            
        except ChatRoom.DoesNotExist:
            logger.error(f"ChatRoom {self.room_id} not found")
        except Exception as e:
            logger.error(f"❌ Error sending message notification: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())