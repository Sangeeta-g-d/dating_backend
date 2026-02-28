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
        """Handle incoming WebSocket messages"""
        try:
            print(f"\n📨 [RECEIVE] Raw WebSocket data received: {text_data}")
            data = json.loads(text_data)
            print(f"📨 [RECEIVE] Parsed JSON data: {data}")
            event = data.get("event")
            print(f"📨 [RECEIVE] Event type: {event}")
            
            if event == "send_message":
                print(f"📨 [RECEIVE] send_message event detected")
                message_data = data.get("data")
                print(f"📨 [RECEIVE] Message data extracted: {message_data}")
                await self.handle_send_message(message_data)
            elif event == "media_message":
                print(f"📨 [RECEIVE] media_message event detected")
                await self.handle_media_message(data.get("data"))
            else:
                logger.warning(f"Unknown event type: {event}")
                await self.send(json.dumps({
                    "event": "error",
                    "data": {"message": f"Unknown event type: {event}"}
                }))
        
        except json.JSONDecodeError as e:
            print(f"❌ [RECEIVE] Failed to decode JSON: {str(e)}")
            logger.error(f"Failed to decode WebSocket message: {str(e)}")
            await self.send(json.dumps({
                "event": "error",
                "data": {"message": "Invalid JSON format"}
            }))
        except Exception as e:
            print(f"❌ [RECEIVE] Error in receive: {str(e)}")
            logger.error(f"Error in receive: {str(e)}")
            await self.send(json.dumps({
                "event": "error",
                "data": {"message": f"Server error: {str(e)}"}
            }))

    async def handle_send_message(self, data):
        """Handle text message sending"""
        try:
            print(f"\n✉️ [SEND_MESSAGE] Handler called with data: {data}")
            print(f"✉️ [SEND_MESSAGE] Data type: {type(data)}")
            print(f"✉️ [SEND_MESSAGE] Data is None: {data is None}")
            
            # Validate data exists
            if not data:
                print(f"❌ [SEND_MESSAGE] Data is None or empty")
                logger.error("Data is None or empty in handle_send_message")
                await self.send(json.dumps({
                    "event": "error",
                    "data": {"message": "Missing required fields - data is empty"}
                }))
                return

            room_id = data.get("roomId")
            message_type = data.get("type")  # "text", "image", "video"
            content = data.get("content")
            attachments = data.get("attachments")

            print(f"✉️ [SEND_MESSAGE] Extracted fields:")
            print(f"   - roomId: {room_id} (type: {type(room_id)})")
            print(f"   - type: {message_type} (type: {type(message_type)})")
            print(f"   - content: {content} (type: {type(content)})")
            print(f"   - attachments: {attachments}")

            # Validate required fields
            print(f"✉️ [SEND_MESSAGE] Validation checks:")
            print(f"   - room_id bool: {bool(room_id)}")
            print(f"   - message_type bool: {bool(message_type)}")
            print(f"   - content bool: {bool(content)}")
            
            if not room_id or not message_type or not content:
                print(f"❌ [SEND_MESSAGE] Validation failed - missing fields")
                logger.error(f"Missing fields - room_id: {room_id}, type: {message_type}, content: {content}")
                await self.send(json.dumps({
                    "event": "error",
                    "data": {"message": "Missing required fields: roomId, type, and content are required"}
                }))
                return

            print(f"✉️ [SEND_MESSAGE] Validation passed - creating message")

            # Create message in database
            message = await self.create_message(room_id, message_type, content, attachments)
            
            if not message:
                print(f"❌ [SEND_MESSAGE] Failed to create message")
                await self.send(json.dumps({
                    "event": "error",
                    "data": {"message": "Failed to create message"}
                }))
                return

            print(f"✉️ [SEND_MESSAGE] Message created successfully - ID: {message.id}")

            # Create message receipts for both participants
            print(f"✉️ [SEND_MESSAGE] Creating message receipts")
            await self.create_message_receipts(message.id)
            print(f"✉️ [SEND_MESSAGE] Message receipts created")

            # Broadcast new message event to room
            print(f"✉️ [SEND_MESSAGE] Broadcasting message to room {room_id}")
            await self.broadcast_new_message(message)
            print(f"✉️ [SEND_MESSAGE] Message broadcasted successfully")

        except Exception as e:
            print(f"❌ [SEND_MESSAGE] Exception occurred: {str(e)}")
            import traceback
            traceback.print_exc()
            logger.error(f"Error in handle_send_message: {str(e)}")
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

    @database_sync_to_async
    def has_room_access(self):
        """Check if user is a participant in this chat room"""
        try:
            room = ChatRoom.objects.get(id=self.room_id)
            return room.user_a == self.user or room.user_b == self.user
        except ChatRoom.DoesNotExist:
            return False

    @database_sync_to_async
    def create_message(self, room_id, message_type, content, attachments=None):
        """Create a message in the database"""
        try:
            print(f"\n💾 [CREATE_MESSAGE] Starting message creation")
            print(f"   - room_id: {room_id}")
            print(f"   - message_type: {message_type}")
            print(f"   - content: {content}")
            print(f"   - sender: {self.user}")
            
            room = ChatRoom.objects.get(id=room_id)
            print(f"💾 [CREATE_MESSAGE] Room found: {room}")
            
            # Encrypt text content if it's a text message
            encrypted_content = None
            if message_type == "text" and content:
                print(f"💾 [CREATE_MESSAGE] Encrypting text content")
                encrypted_content = encrypt_text(content)
                print(f"💾 [CREATE_MESSAGE] Text encrypted successfully")
            
            print(f"💾 [CREATE_MESSAGE] Creating Message object with:")
            print(f"   - room: {room}")
            print(f"   - sender: {self.user}")
            print(f"   - content_encrypted: {encrypted_content[:20] if encrypted_content else 'None'}...")
            print(f"   - media_type: {message_type if message_type in ['image', 'video'] else ''}")
            
            message = Message.objects.create(
                room=room,
                sender=self.user,
                content_encrypted=encrypted_content,
                media_type=message_type if message_type in ["image", "video"] else "",
                created_at=timezone.now(),
            )
            
            print(f"💾 [CREATE_MESSAGE] Message created successfully - ID: {message.id}")
            return message
        except ChatRoom.DoesNotExist:
            print(f"❌ [CREATE_MESSAGE] Chat room {room_id} does not exist")
            logger.error(f"Chat room {room_id} does not exist")
            return None
        except Exception as e:
            print(f"❌ [CREATE_MESSAGE] Error creating message: {str(e)}")
            import traceback
            traceback.print_exc()
            logger.error(f"Error creating message: {str(e)}")
            return None

    @database_sync_to_async
    def create_message_receipts(self, message_id):
        """Create message receipts for all participants"""
        try:
            print(f"\n📋 [CREATE_RECEIPTS] Creating receipts for message {message_id}")
            message = Message.objects.get(id=message_id)
            room = message.room
            
            print(f"📋 [CREATE_RECEIPTS] Room participants: {room.participants()}")
            
            # Create receipt for both participants
            for user in room.participants():
                receipt, created = MessageReceipt.objects.get_or_create(
                    message=message,
                    user=user
                )
                print(f"📋 [CREATE_RECEIPTS] Receipt for {user.email}: {'created' if created else 'exists'}")
            
            print(f"📋 [CREATE_RECEIPTS] All receipts created successfully")
        except Exception as e:
            print(f"❌ [CREATE_RECEIPTS] Error: {str(e)}")
            import traceback
            traceback.print_exc()
            logger.error(f"Error creating message receipts: {str(e)}")

    async def broadcast_new_message(self, message):
        """Broadcast new message event to all users in the room"""
        try:
            print(f"\n📡 [BROADCAST] Starting broadcast for message {message.id}")
            message_data = await self.format_message_data(message)
            print(f"📡 [BROADCAST] Formatted message data: {message_data}")
            
            print(f"📡 [BROADCAST] Broadcasting to group: {self.room_group_name}")
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "new_message_broadcast",
                    "data": message_data
                }
            )
            print(f"📡 [BROADCAST] Message broadcast successful")
        except Exception as e:
            print(f"❌ [BROADCAST] Error: {str(e)}")
            import traceback
            traceback.print_exc()
            logger.error(f"Error broadcasting message: {str(e)}")

    @database_sync_to_async
    def format_message_data(self, message):
        """Format message data according to the specified format"""
        print(f"\n📝 [FORMAT_MESSAGE] Formatting message {message.id}")
        sender = message.sender
        content = ""
        
        print(f"📝 [FORMAT_MESSAGE] Message details:")
        print(f"   - sender: {sender.email}")
        print(f"   - media_type: {message.media_type}")
        print(f"   - is_deleted: {message.is_deleted}")
        print(f"   - has encrypted content: {bool(message.content_encrypted)}")
        
        if message.media_type == "text" and message.content_encrypted:
            from .models import decrypt_text
            try:
                print(f"📝 [FORMAT_MESSAGE] Decrypting content...")
                content = decrypt_text(message.content_encrypted)
                print(f"📝 [FORMAT_MESSAGE] Decrypted content: {content}")
            except Exception as decrypt_err:
                print(f"📝 [FORMAT_MESSAGE] Decryption failed: {str(decrypt_err)}")
                content = ""
        
        formatted_data = {
            "messageId": message.id,
            "sender_id": sender.id,
            "type": message.media_type if message.media_type else "text",
            "content": content,
            "attachments": None,
            "createdAt": format_to_ist(message.created_at)
        }
        
        print(f"📝 [FORMAT_MESSAGE] Formatted data: {formatted_data}")
        return formatted_data

    # Handler methods for channel layer messages
    async def new_message_broadcast(self, event):
        """Send incoming message event to WebSocket"""
        await self.send(json.dumps({
            "event": "new_message",
            "data": event["data"]
        }))

    async def media_message_broadcast(self, event):
        """Send media message event to WebSocket"""
        await self.send(json.dumps({
            "event": "media_message",
            "data": event["data"]
        }))

    async def media_message(self, event):
        """Alternative handler for media messages from API"""
        await self.send(json.dumps({
            "event": "media_message",
            "data": event.get("message", event.get("data"))
        }))