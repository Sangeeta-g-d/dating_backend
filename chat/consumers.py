import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
import logging
from .tasks import send_message_notification_task

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
        logger.info(f"WebSocket disconnected - Code: {close_code}, User: {self.user.id if hasattr(self, 'user') else 'Unknown'}, Room: {self.room_id if hasattr(self, 'room_id') else 'Unknown'}")
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            logger.info(f"📨 Raw data received from user {self.user.id}: {text_data[:200]}")
            
            data = json.loads(text_data)
            msg_type = data.get("type")
            
            logger.info(f"📨 Parsed message type: '{msg_type}' from user {self.user.id} in room {self.room_id}")

            # ----------------- TYPING INDICATOR -----------------
            if msg_type == "typing":
                is_typing = data.get("is_typing", False)
                logger.info(f"⌨️ Typing indicator - User {self.user.id} is_typing: {is_typing}")
                
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "typing_event",
                        "user_id": self.user.id,
                        "user_name": getattr(self.user, 'full_name', ''),
                        "is_typing": is_typing,
                    }
                )
                logger.info(f"✅ Typing indicator sent to room group")
                return

            # ----------------- SEND MESSAGE -----------------
            if msg_type == "message":
                message_text = data.get("message")
                reply_to_id = data.get("reply_to")
                
                logger.info(f"💬 Processing message from user {self.user.id} in room {self.room_id}")
                logger.info(f"💬 Message text: '{message_text[:100] if message_text else 'EMPTY'}...'")
                logger.info(f"💬 Reply to: {reply_to_id}")

                # Save message
                logger.info(f"💾 Saving message to database...")
                msg_obj = await self.save_message(message_text, reply_to_id)
                logger.info(f"✅ Message saved successfully with ID: {msg_obj.id}")
                
                # Create receipts
                logger.info(f"📝 Creating receipts for message {msg_obj.id}...")
                await self.create_receipts(msg_obj)
                logger.info(f"✅ Receipts created successfully for message {msg_obj.id}")

                # Queue notification task
                try:
                    logger.info(f"📤 Attempting to queue notification task for message {msg_obj.id}")
                    logger.info(f"📤 Task params - room_id: {self.room_id}, sender_id: {self.user.id}, message_id: {msg_obj.id}")
                    
                    task_result = send_message_notification_task.delay(
                        self.room_id,
                        self.user.id,
                        msg_obj.id,
                        message_text
                    )
                    
                    logger.info(f"✅ Notification task queued successfully with task ID: {task_result.id}")
                except Exception as e:
                    logger.error(f"❌ Failed to queue notification task: {str(e)}")
                    import traceback
                    logger.error(f"❌ Traceback: {traceback.format_exc()}")

                # Broadcast to room
                logger.info(f"📡 Broadcasting message {msg_obj.id} to room group {self.room_group_name}")
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
                logger.info(f"✅ Message {msg_obj.id} broadcast complete")
                return

            # ----------------- MARK SEEN -----------------
            if msg_type == "seen":
                message_ids = data.get("message_ids", [])
                
                logger.info(f"👁️ Mark as seen request from user {self.user.id}")
                logger.info(f"👁️ Message IDs to mark: {message_ids}")

                if isinstance(message_ids, int):  
                    message_ids = [message_ids]
                    logger.info(f"👁️ Converted single ID to list: {message_ids}")

                seen_list = await self.mark_multiple_as_seen(message_ids)
                logger.info(f"✅ Messages marked as seen at: {seen_list['timestamp']}")

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
                logger.info(f"✅ Seen event broadcast complete")
                return
            
            logger.warning(f"⚠️ Unknown message type received: {msg_type}")
                
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON decode error: {str(e)}")
            logger.error(f"❌ Raw data was: {text_data}")
        except Exception as e:
            logger.error(f"❌ Error in receive() method: {str(e)}")
            import traceback
            logger.error(f"❌ Full traceback: {traceback.format_exc()}")

    # ======================================================
    #                   EVENT HANDLERS
    # ======================================================

    async def typing_event(self, event):
        logger.info(f"📤 Sending typing event to client - user_id: {event['user_id']}, is_typing: {event['is_typing']}")
        await self.send(text_data=json.dumps({
            "event": "typing",
            "user_id": event["user_id"],
            "user_name": event.get("user_name", ""),
            "is_typing": event["is_typing"],
        }))

    async def chat_message(self, event):
        logger.info(f"📤 Sending chat message to client - message_id: {event.get('message_id')}, event: {event.get('event')}")
        await self.send(text_data=json.dumps(event))

    async def seen_event(self, event):
        logger.info(f"📤 Sending seen event to client - message_ids: {event.get('message_ids')}, user_id: {event.get('user_id')}")
        await self.send(text_data=json.dumps(event))

    async def media_message(self, event):
        logger.info(f"📤 Sending media message to client")
        await self.send(text_data=json.dumps({
            "type": "media_message",
            "data": event["message"]
        }))

    async def chat_delete(self, event):
        logger.info(f"📤 Sending chat delete event to client")
        await self.send(text_data=json.dumps(event["data"]))

    # ======================================================
    #                   DATABASE HELPERS
    # ======================================================

    @database_sync_to_async
    def has_room_access(self):
        from chat.models import ChatRoom
        try:
            logger.info(f"🔍 Checking room access for user {self.user.id} in room {self.room_id}")
            room = ChatRoom.objects.get(id=self.room_id)
            has_access = self.user in [room.user_a, room.user_b]
            logger.info(f"🔍 Room access check result - Room {self.room_id}, User {self.user.id}, Access: {has_access}")
            return has_access
        except ChatRoom.DoesNotExist:
            logger.error(f"❌ Room {self.room_id} does not exist")
            return False
        except Exception as e:
            logger.error(f"❌ Error checking room access: {str(e)}")
            return False
        
    @database_sync_to_async
    def save_message(self, text, reply_to_id=None):
        from chat.models import ChatRoom, Message
        
        try:
            logger.info(f"💾 DB: Fetching room {self.room_id}")
            room = ChatRoom.objects.get(id=self.room_id)
            logger.info(f"💾 DB: Room found - {room}")
        
            reply_obj = None
            if reply_to_id:
                try:
                    logger.info(f"💾 DB: Fetching reply message {reply_to_id}")
                    reply_obj = Message.objects.get(id=reply_to_id, room=room)
                    logger.info(f"💾 DB: Reply message found")
                except Message.DoesNotExist:
                    logger.warning(f"⚠️ DB: Reply message {reply_to_id} not found")
                    reply_obj = None
        
            logger.info(f"💾 DB: Creating message object")
            msg = Message(
                room=room,
                sender=self.user,
                reply_to=reply_obj
            )
            logger.info(f"💾 DB: Setting message content (encryption will occur)")
            msg.content = text  # encryption handled in setter
            logger.info(f"💾 DB: Saving message to database")
            msg.save()
            logger.info(f"💾 DB: Message saved successfully with ID {msg.id}")
            return msg
        except Exception as e:
            logger.error(f"❌ DB: Error saving message: {str(e)}")
            import traceback
            logger.error(f"❌ DB: Traceback: {traceback.format_exc()}")
            raise

    @database_sync_to_async
    def create_receipts(self, message_obj):
        from chat.models import ChatRoom, MessageReceipt

        try:
            logger.info(f"📝 DB: Creating receipts for message {message_obj.id}")
            room = ChatRoom.objects.get(id=self.room_id)
            participants = room.participants()
            logger.info(f"📝 DB: Room has {len(participants)} participants")

            for user in participants:
                logger.info(f"📝 DB: Creating receipt for user {user.id}")
                receipt, created = MessageReceipt.objects.get_or_create(
                    message=message_obj, user=user
                )
                logger.info(f"📝 DB: Receipt {'created' if created else 'already exists'} for user {user.id}")
                
                if user.id == message_obj.sender_id:
                    logger.info(f"📝 DB: Marking receipt as delivered for sender {user.id}")
                    receipt.mark_delivered()

            logger.info(f"✅ DB: All receipts created for message {message_obj.id}")
            return True
        except Exception as e:
            logger.error(f"❌ DB: Error creating receipts: {str(e)}")
            import traceback
            logger.error(f"❌ DB: Traceback: {traceback.format_exc()}")
            return False

    @database_sync_to_async
    def mark_multiple_as_seen(self, message_ids):
        from chat.models import MessageReceipt
        from django.utils import timezone
        
        try:
            logger.info(f"👁️ DB: Marking {len(message_ids)} messages as seen for user {self.user.id}")
            timestamp = timezone.now()
        
            for mid in message_ids:
                try:
                    logger.info(f"👁️ DB: Fetching receipt for message {mid}, user {self.user.id}")
                    receipt = MessageReceipt.objects.get(message_id=mid, user=self.user)
                    receipt.seen_at = timestamp
                    receipt.save()
                    logger.info(f"✅ DB: Message {mid} marked as seen")
                except MessageReceipt.DoesNotExist:
                    logger.warning(f"⚠️ DB: Receipt not found for message {mid}, user {self.user.id}")
                    pass
                except Exception as e:
                    logger.error(f"❌ DB: Error marking message {mid} as seen: {str(e)}")
            
            logger.info(f"✅ DB: All messages marked as seen at {timestamp.isoformat()}")
            return {"timestamp": timestamp.isoformat()}
        except Exception as e:
            logger.error(f"❌ DB: Error in mark_multiple_as_seen: {str(e)}")
            import traceback
            logger.error(f"❌ DB: Traceback: {traceback.format_exc()}")
            return {"timestamp": timezone.now().isoformat()}

    @database_sync_to_async
    def send_message_notification(self, message_obj, message_text):
        """
        Send Firebase push notification to the recipient of the message.
        Does NOT store in notification table - just sends the push notification.
        """
        from chat.models import ChatRoom
        from notifications.utils import send_push_notification
        
        try:
            logger.info(f"🔔 Starting notification process for message {message_obj.id}")
            room = ChatRoom.objects.get(id=self.room_id)
            
            # Determine the recipient (the other person in the chat)
            recipient = room.user_b if room.user_a.id == self.user.id else room.user_a
            logger.info(f"🔔 Recipient identified: {recipient.id} ({recipient.email})")
            
            # Don't send notification if recipient is the sender
            if recipient.id == self.user.id:
                logger.debug("⚠️ Recipient is sender, skipping notification")
                return
            
            # Get sender's name
            sender_name = getattr(self.user, 'full_name', 'Someone')
            logger.info(f"🔔 Sender name: {sender_name}")
            
            # Fetch device tokens for the recipient
            device_tokens = list(
                recipient.device_tokens.values_list("fcm_token", flat=True)
            )
            logger.info(f"🔔 Found {len(device_tokens)} device tokens for recipient")
            
            if not device_tokens:
                logger.debug(f"⚠️ No device tokens found for user {recipient.id}")
                return
            
            # Truncate message for notification (max 50 chars)
            preview = message_text[:50] + "..." if len(message_text) > 50 else message_text
            logger.info(f"🔔 Message preview: '{preview}'")
            
            # Send only sender name and message (no title)
            notification_body = f"{sender_name}: {preview}"
            
            # Data payload for the notification
            data = {
                "room_id": str(self.room_id),
                "message_id": str(message_obj.id),
                "sender_id": str(self.user.id),
                "sender_name": sender_name,
                "type": "new_message",
            }
            
            logger.info(f"📨 Sending message notification to user {recipient.id} (tokens: {len(device_tokens)})")
            
            # Send push notification directly without storing in DB
            send_push_notification(
                device_tokens=device_tokens,
                title="",
                body=notification_body,
                data=data
            )
            
            logger.info(f"✅ Message notification sent successfully")
            
        except ChatRoom.DoesNotExist:
            logger.error(f"❌ ChatRoom {self.room_id} not found")
        except Exception as e:
            logger.error(f"❌ Error sending message notification: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())