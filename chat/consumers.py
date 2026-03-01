import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
import logging
from dating_backend.timezone_utils import format_to_ist
from .models import ChatRoom, Message, MessageReceipt, encrypt_text
from auth_api.models import CustomUser

logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        logger.warning(f"🔌 [CONNECT] ===== CONNECT METHOD START =====")
        self.room_id = self.scope["url_route"]["kwargs"]["room_id"]
        self.room_group_name = f"chat_{self.room_id}"
        self.user = self.scope["user"]

        logger.warning(f"🔌 [CONNECT] Room ID: {self.room_id}")
        logger.warning(f"🔌 [CONNECT] Room Group Name: {self.room_group_name}")
        logger.warning(f"🔌 [CONNECT] User: {self.user}")
        logger.warning(f"🔌 [CONNECT] Is Authenticated: {self.user.is_authenticated}")

        if isinstance(self.user, AnonymousUser) or not self.user.is_authenticated:
            logger.warning(f"❌ [CONNECT] Authentication failed - User is anonymous or not authenticated")
            await self.close(code=4001)
            return
        
        if not await self.has_room_access():
            logger.warning(f"❌ [CONNECT] Room access denied - User {self.user.id} cannot access room {self.room_id}")
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        logger.warning(f"✅ [CONNECT] WebSocket connection accepted - User {self.user.id} in room {self.room_id}")
        logger.warning(f"✅ [CONNECT] Channel name: {self.channel_name}")
        logger.warning(f"✅ [CONNECT] Channel layer: {self.channel_layer}")

    async def disconnect(self, close_code):
        logger.warning(f"🔌 [DISCONNECT] ===== DISCONNECT METHOD CALLED =====")
        logger.warning(f"🔌 [DISCONNECT] Close code: {close_code}")
        logger.warning(f"🔌 [DISCONNECT] Room: {self.room_id}, User: {self.user}")
        try:
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
            logger.warning(f"✅ [DISCONNECT] User {self.user.id} removed from group {self.room_group_name}")
        except Exception as e:
            logger.error(f"❌ [DISCONNECT] Error during disconnect: {str(e)}", exc_info=True)

    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        logger.warning(f"🔔 [RECEIVE] ===== RECEIVE METHOD CALLED =====")
        logger.warning(f"🔔 [RECEIVE] Raw text_data: {text_data}")
        logger.warning(f"🔔 [RECEIVE] text_data type: {type(text_data)}")
        logger.warning(f"🔔 [RECEIVE] text_data length: {len(text_data) if text_data else 0}")
        
        try:
            logger.info(f"📨 [RECEIVE] Raw WebSocket data received: {text_data}")
            data = json.loads(text_data)
            logger.info(f"📨 [RECEIVE] Parsed JSON data: {data}")
            event = data.get("event")
            logger.info(f"📨 [RECEIVE] Event type: {event}")
            
            if event == "send_message":
                logger.info(f"📨 [RECEIVE] send_message event detected")
                message_data = data.get("data")
                logger.info(f"📨 [RECEIVE] Message data extracted: {message_data}")
                await self.handle_send_message(message_data)
            elif event == "media_message":
                logger.info(f"📨 [RECEIVE] media_message event detected")
                await self.handle_media_message(data.get("data"))
            elif event == "mark_seen":
                logger.info(f"📨 [RECEIVE] mark_seen event detected")
                mark_seen_data = data.get("data")
                logger.info(f"📨 [RECEIVE] Mark seen data extracted: {mark_seen_data}")
                await self.handle_mark_seen(mark_seen_data)
            else:
                logger.warning(f"🔔 [RECEIVE] Unknown event type: {event}")
                await self.send(json.dumps({
                    "event": "error",
                    "data": {"message": f"Unknown event type: {event}"}
                }))
        
        except json.JSONDecodeError as e:
            logger.error(f"❌ [RECEIVE] Failed to decode JSON: {str(e)}")
            logger.error(f"❌ [RECEIVE] Raw data was: {text_data}")
            try:
                await self.send(json.dumps({
                    "event": "error",
                    "data": {"message": "Invalid JSON format"}
                }))
            except Exception as send_err:
                logger.error(f"❌ [RECEIVE] Failed to send error response: {str(send_err)}")
        except Exception as e:
            logger.error(f"❌ [RECEIVE] Unexpected error in receive: {str(e)}", exc_info=True)
            try:
                await self.send(json.dumps({
                    "event": "error",
                    "data": {"message": f"Server error: {str(e)}"}
                }))
            except Exception as send_err:
                logger.error(f"❌ [RECEIVE] Failed to send error response: {str(send_err)}")

    async def handle_send_message(self, data):
        """Handle text message sending"""
        try:
            logger.info(f"✉️ [SEND_MESSAGE] Handler called with data: {data}")
            logger.info(f"✉️ [SEND_MESSAGE] Data type: {type(data)}")
            logger.info(f"✉️ [SEND_MESSAGE] Data is None: {data is None}")
            
            # Validate data exists
            if not data:
                logger.error("❌ [SEND_MESSAGE] Data is None or empty")
                await self.send(json.dumps({
                    "event": "error",
                    "data": {"message": "Missing required fields - data is empty"}
                }))
                return

            room_id = data.get("roomId")
            message_type = data.get("type")  # "text", "image", "video"
            content = data.get("content")
            attachments = data.get("attachments")

            logger.info(f"✉️ [SEND_MESSAGE] Extracted fields:")
            logger.info(f"   - roomId: {room_id} (type: {type(room_id).__name__})")
            logger.info(f"   - type: {message_type} (type: {type(message_type).__name__})")
            logger.info(f"   - content: {content} (type: {type(content).__name__})")
            logger.info(f"   - attachments: {attachments}")

            # Validate required fields
            logger.info(f"✉️ [SEND_MESSAGE] Validation checks:")
            logger.info(f"   - room_id bool: {bool(room_id)}")
            logger.info(f"   - message_type bool: {bool(message_type)}")
            logger.info(f"   - content bool: {bool(content)}")
            
            if not room_id or not message_type or not content:
                logger.error(f"❌ [SEND_MESSAGE] Validation failed - missing fields")
                logger.error(f"Missing fields - room_id: {room_id}, type: {message_type}, content: {content}")
                await self.send(json.dumps({
                    "event": "error",
                    "data": {"message": "Missing required fields: roomId, type, and content are required"}
                }))
                return

            logger.info(f"✉️ [SEND_MESSAGE] Validation passed - creating message")

            # Create message in database
            message = await self.create_message(room_id, message_type, content, attachments)
            
            if not message:
                logger.error(f"❌ [SEND_MESSAGE] Failed to create message")
                await self.send(json.dumps({
                    "event": "error",
                    "data": {"message": "Failed to create message"}
                }))
                return

            logger.info(f"✉️ [SEND_MESSAGE] Message created successfully - ID: {message.id}")

            # Create message receipts for both participants
            logger.info(f"✉️ [SEND_MESSAGE] Creating message receipts")
            await self.create_message_receipts(message.id)
            logger.info(f"✉️ [SEND_MESSAGE] Message receipts created")

            # Broadcast new message event to room
            logger.info(f"✉️ [SEND_MESSAGE] Broadcasting message to room {room_id}")
            await self.broadcast_new_message(message)
            logger.info(f"✉️ [SEND_MESSAGE] Message broadcasted successfully")

        except Exception as e:
            logger.error(f"❌ [SEND_MESSAGE] Exception occurred: {str(e)}", exc_info=True)
            await self.send(json.dumps({
                "event": "error",
                "data": {"message": str(e)}
            }))

    async def handle_media_message(self, data):
        """Handle media message broadcasting - just forward the media URL"""
        try:
            # The media has already been saved via MediaMessageUploadAPIView
            # We just broadcast the media data to the chat room
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "media_message_broadcast",
                    "data": data
                }
            )
        except Exception as e:
            logger.error(f"Error in handle_media_message: {str(e)}")

    async def handle_mark_seen(self, data):
        """Mark messages as seen and broadcast"""
        try:
            logger.info(f"👁️ [MARK_SEEN] Handling mark_seen event")
            room_id = data.get("roomId")
            last_seen_message_id = data.get("lastSeenMessageId")
            
            logger.info(f"👁️ [MARK_SEEN] room_id: {room_id}, last_seen_message_id: {last_seen_message_id}")
            
            if not room_id or not last_seen_message_id:
                logger.error(f"❌ [MARK_SEEN] Missing required fields")
                await self.send(json.dumps({
                    "event": "error",
                    "data": {"message": "Missing required fields: roomId and lastSeenMessageId"}
                }))
                return
            
            # Mark messages as seen in database
            await self.mark_messages_as_seen(room_id, last_seen_message_id)
            
            # Broadcast seen status to room
            await self.broadcast_messages_seen(room_id, last_seen_message_id)
            
            logger.info(f"✅ [MARK_SEEN] Messages marked as seen and broadcasted")
            
        except Exception as e:
            logger.error(f"❌ [MARK_SEEN] Error: {str(e)}", exc_info=True)
            await self.send(json.dumps({
                "event": "error",
                "data": {"message": str(e)}
            }))

    @database_sync_to_async
    def has_room_access(self):
        """Check if user is a participant in this chat room"""
        try:
            logger.info(f"🔐 [HAS_ROOM_ACCESS] Checking access - Room: {self.room_id}, User: {self.user.id}")
            room = ChatRoom.objects.get(id=self.room_id)
            logger.info(f"🔐 [HAS_ROOM_ACCESS] Room found: user_a={room.user_a.id}, user_b={room.user_b.id}")
            has_access = room.user_a == self.user or room.user_b == self.user
            logger.info(f"🔐 [HAS_ROOM_ACCESS] Access result: {has_access}")
            return has_access
        except ChatRoom.DoesNotExist:
            logger.error(f"❌ [HAS_ROOM_ACCESS] Chat room {self.room_id} does not exist")
            return False
        except Exception as e:
            logger.error(f"❌ [HAS_ROOM_ACCESS] Error checking access: {str(e)}", exc_info=True)
            return False

    @database_sync_to_async
    def create_message(self, room_id, message_type, content, attachments=None):
        """Create a message in the database"""
        try:
            logger.info(f"💾 [CREATE_MESSAGE] Starting message creation")
            logger.info(f"   - room_id: {room_id}")
            logger.info(f"   - message_type: {message_type}")
            logger.info(f"   - content: {content}")
            logger.info(f"   - sender: {self.user}")
            
            room = ChatRoom.objects.get(id=room_id)
            logger.info(f"💾 [CREATE_MESSAGE] Room found: {room}")
            
            # Encrypt text content if it's a text message
            encrypted_content = None
            if message_type == "text" and content:
                logger.info(f"💾 [CREATE_MESSAGE] Encrypting text content")
                encrypted_content = encrypt_text(content)
                logger.info(f"💾 [CREATE_MESSAGE] Text encrypted successfully")
            
            logger.info(f"💾 [CREATE_MESSAGE] Creating Message object with:")
            logger.info(f"   - room: {room}")
            logger.info(f"   - sender: {self.user}")
            logger.info(f"   - content_encrypted: {encrypted_content[:20] if encrypted_content else 'None'}...")
            logger.info(f"   - media_type: {message_type if message_type in ['image', 'video'] else ''}")
            
            message = Message.objects.create(
                room=room,
                sender=self.user,
                content_encrypted=encrypted_content,
                media_type=message_type if message_type in ["image", "video"] else "text",
                created_at=timezone.now(),
            )
            
            logger.info(f"💾 [CREATE_MESSAGE] Message created successfully - ID: {message.id}")
            return message
        except ChatRoom.DoesNotExist:
            logger.error(f"❌ [CREATE_MESSAGE] Chat room {room_id} does not exist")
            return None
        except Exception as e:
            logger.error(f"❌ [CREATE_MESSAGE] Error creating message: {str(e)}", exc_info=True)
            return None

    @database_sync_to_async
    def create_message_receipts(self, message_id):
        """Create message receipts for all participants"""
        try:
            logger.info(f"📋 [CREATE_RECEIPTS] Creating receipts for message {message_id}")
            message = Message.objects.get(id=message_id)
            room = message.room
            
            logger.info(f"📋 [CREATE_RECEIPTS] Room participants: {room.participants()}")
            
            # Create receipt for both participants
            for user in room.participants():
                receipt, created = MessageReceipt.objects.get_or_create(
                    message=message,
                    user=user
                )
                logger.info(f"📋 [CREATE_RECEIPTS] Receipt for {user.email}: {'created' if created else 'exists'}")
            
            logger.info(f"📋 [CREATE_RECEIPTS] All receipts created successfully")
        except Exception as e:
            logger.error(f"❌ [CREATE_RECEIPTS] Error: {str(e)}", exc_info=True)

    async def broadcast_new_message(self, message):
        """Broadcast new message event to all users in the room"""
        try:
            logger.info(f"📡 [BROADCAST] Starting broadcast for message {message.id}")
            message_data = await self.format_message_data(message)
            logger.info(f"📡 [BROADCAST] Formatted message data: {message_data}")
            
            logger.info(f"📡 [BROADCAST] Broadcasting to group: {self.room_group_name}")
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "new_message_broadcast",
                    "data": message_data
                }
            )
            logger.info(f"📡 [BROADCAST] Message broadcast successful")
        except Exception as e:
            logger.error(f"❌ [BROADCAST] Error: {str(e)}", exc_info=True)

    @database_sync_to_async
    def format_message_data(self, message):
        """Format message data according to the specified format"""
        logger.info(f"📝 [FORMAT_MESSAGE] Formatting message {message.id}")
        sender = message.sender
        content = ""
        
        logger.info(f"📝 [FORMAT_MESSAGE] Message details:")
        logger.info(f"   - sender: {sender.email}")
        logger.info(f"   - media_type: '{message.media_type}'")
        logger.info(f"   - is_deleted: {message.is_deleted}")
        logger.info(f"   - content_encrypted: {message.content_encrypted[:50] if message.content_encrypted else 'None'}...")
        
        # Decrypt text if it has encrypted content
        if message.content_encrypted:
            from .models import decrypt_text
            try:
                logger.info(f"📝 [FORMAT_MESSAGE] Attempting to decrypt content...")
                content = decrypt_text(message.content_encrypted)
                logger.warning(f"✅ [FORMAT_MESSAGE] Successfully decrypted: {content}")
            except Exception as decrypt_err:
                logger.error(f"❌ [FORMAT_MESSAGE] Decryption failed: {str(decrypt_err)}", exc_info=True)
                content = ""
        else:
            logger.warning(f"⚠️ [FORMAT_MESSAGE] No encrypted content to decrypt")
        
        formatted_data = {
            "messageId": message.id,
            "sender_id": sender.id,
            "type": message.media_type if message.media_type else "text",
            "content": content,
            "attachments": None,
            "createdAt": format_to_ist(message.created_at)
        }
        
        logger.info(f"📝 [FORMAT_MESSAGE] Formatted data: {formatted_data}")
        return formatted_data

    @database_sync_to_async
    def mark_messages_as_seen(self, room_id, last_seen_message_id):
        """Mark messages as seen in database"""
        try:
            logger.info(f"👁️ [DB_MARK_SEEN] Marking messages as seen up to {last_seen_message_id}")
            
            # Get all messages up to and including the last_seen_message_id
            messages = Message.objects.filter(
                room_id=room_id,
                id__lte=last_seen_message_id
            ).exclude(sender=self.user)  # Don't mark own messages
            
            logger.info(f"👁️ [DB_MARK_SEEN] Found {messages.count()} messages to mark as seen")
            
            # Mark each message as seen for both receiver and sender
            for message in messages:
                try:
                    # Update receiver's receipt (the user marking as seen)
                    receiver_receipt = MessageReceipt.objects.get(message=message, user=self.user)
                    receiver_receipt.mark_seen()
                    logger.info(f"👁️ [DB_MARK_SEEN] Message {message.id} marked as seen for receiver {self.user.id}")
                    
                    # Also update sender's receipt so they see it as seen on their side
                    sender_receipt = MessageReceipt.objects.get(message=message, user=message.sender)
                    sender_receipt.mark_seen()
                    logger.info(f"👁️ [DB_MARK_SEEN] Message {message.id} also marked as seen for sender {message.sender.id}")
                    
                except MessageReceipt.DoesNotExist as e:
                    logger.warning(f"⚠️ [DB_MARK_SEEN] No receipt found for message {message.id}: {str(e)}")
            
            logger.info(f"✅ [DB_MARK_SEEN] All messages marked as seen in database")
            
        except Exception as e:
            logger.error(f"❌ [DB_MARK_SEEN] Error marking messages as seen: {str(e)}", exc_info=True)

    async def broadcast_messages_seen(self, room_id, last_seen_message_id):
        """Broadcast that messages have been seen"""
        try:
            logger.info(f"📡 [BROADCAST_SEEN] Broadcasting messages_seen event")
            
            seen_data = {
                "roomId": room_id,
                "userId": self.user.id,
                "lastSeenMessageId": last_seen_message_id,
                "seenAt": timezone.now().isoformat()
            }
            
            logger.info(f"📡 [BROADCAST_SEEN] Sending to group: {seen_data}")
            
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "messages_seen_broadcast",
                    "data": seen_data
                }
            )
            
            logger.info(f"✅ [BROADCAST_SEEN] messages_seen broadcasted successfully")
            
        except Exception as e:
            logger.error(f"❌ [BROADCAST_SEEN] Error broadcasting: {str(e)}", exc_info=True)

    # Handler methods for channel layer messages
    async def new_message_broadcast(self, event):
        """Send incoming message event to WebSocket"""
        logger.warning(f"📤 [NEW_MESSAGE_BROADCAST] Handler called with event: {event}")
        try:
            response = {
                "event": "new_message",
                "data": event["data"]
            }
            logger.info(f"📤 [NEW_MESSAGE_BROADCAST] Sending to WebSocket: {response}")
            await self.send(json.dumps(response))
            logger.warning(f"✅ [NEW_MESSAGE_BROADCAST] Message sent successfully")
        except Exception as e:
            logger.error(f"❌ [NEW_MESSAGE_BROADCAST] Error sending message: {str(e)}", exc_info=True)

    async def media_message_broadcast(self, event):
        """Send media message event to WebSocket"""
        logger.warning(f"📤 [MEDIA_MESSAGE_BROADCAST] Handler called with event: {event}")
        try:
            response = {
                "event": "media_message",
                "data": event["data"]
            }
            logger.info(f"📤 [MEDIA_MESSAGE_BROADCAST] Sending to WebSocket: {response}")
            await self.send(json.dumps(response))
            logger.warning(f"✅ [MEDIA_MESSAGE_BROADCAST] Message sent successfully")
        except Exception as e:
            logger.error(f"❌ [MEDIA_MESSAGE_BROADCAST] Error sending message: {str(e)}", exc_info=True)

    async def media_message(self, event):
        """Alternative handler for media messages from API"""
        logger.warning(f"📤 [MEDIA_MESSAGE] Handler called with event: {event}")
        try:
            response = {
                "event": "media_message",
                "data": event.get("message", event.get("data"))
            }
            logger.info(f"📤 [MEDIA_MESSAGE] Sending to WebSocket: {response}")
            await self.send(json.dumps(response))
            logger.warning(f"✅ [MEDIA_MESSAGE] Message sent successfully")
        except Exception as e:
            logger.error(f"❌ [MEDIA_MESSAGE] Error sending message: {str(e)}", exc_info=True)

    async def messages_seen_broadcast(self, event):
        """Handle messages_seen broadcast event"""
        logger.warning(f"👁️ [MESSAGES_SEEN_BROADCAST] Handler called with event: {event}")
        try:
            response = {
                "event": "messages_seen",
                "data": event["data"]
            }
            logger.info(f"👁️ [MESSAGES_SEEN_BROADCAST] Sending to WebSocket: {response}")
            await self.send(json.dumps(response))
            logger.warning(f"✅ [MESSAGES_SEEN_BROADCAST] Seen event sent successfully")
        except Exception as e:
            logger.error(f"❌ [MESSAGES_SEEN_BROADCAST] Error sending seen event: {str(e)}", exc_info=True)