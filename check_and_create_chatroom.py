"""
Django shell script to check and create missing ChatRooms for matched users.
Run with: python manage.py shell < check_and_create_chatroom.py
"""

from auth_api.models import CustomUser
from chat.models import ChatRoom
from swipe_feature.models import Match

def check_chatroom(user_id_1, user_id_2):
    """Check if ChatRoom exists between two users."""
    # Ensure consistent ordering (smaller ID first)
    user_a_id = min(user_id_1, user_id_2)
    user_b_id = max(user_id_1, user_id_2)
    
    try:
        chatroom = ChatRoom.objects.get(user_a_id=user_a_id, user_b_id=user_b_id)
        print(f"✓ ChatRoom FOUND: ID {chatroom.id}")
        print(f"  - User A: {chatroom.user_a.email} (ID: {chatroom.user_a.id})")
        print(f"  - User B: {chatroom.user_b.email} (ID: {chatroom.user_b.id})")
        print(f"  - Created: {chatroom.created_at}")
        print(f"  - Last Message: {chatroom.last_message_at or 'None'}")
        return chatroom
    except ChatRoom.DoesNotExist:
        print(f"✗ ChatRoom NOT FOUND for users {user_a_id} and {user_b_id}")
        return None

def create_chatroom(user_id_1, user_id_2):
    """Create ChatRoom between two users if it doesn't exist."""
    # Ensure consistent ordering
    user_a_id = min(user_id_1, user_id_2)
    user_b_id = max(user_id_1, user_id_2)
    
    try:
        user_a = CustomUser.objects.get(id=user_a_id)
        user_b = CustomUser.objects.get(id=user_b_id)
    except CustomUser.DoesNotExist as e:
        print(f"✗ ERROR: User not found - {e}")
        return None
    
    chatroom, created = ChatRoom.objects.get_or_create(
        user_a=user_a,
        user_b=user_b
    )
    
    if created:
        print(f"✓ ChatRoom CREATED: ID {chatroom.id}")
        print(f"  - User A: {chatroom.user_a.email} (ID: {chatroom.user_a.id})")
        print(f"  - User B: {chatroom.user_b.email} (ID: {chatroom.user_b.id})")
        return chatroom
    else:
        print(f"✓ ChatRoom already existed: ID {chatroom.id}")
        return chatroom

def fix_all_matches_without_chatrooms():
    """Find all matches without ChatRooms and create them."""
    print("\n=== CHECKING ALL MATCHES ===\n")
    
    all_matches = Match.objects.select_related('user1', 'user2').all()
    missing_count = 0
    created_count = 0
    
    for match in all_matches:
        user_a_id = min(match.user1.id, match.user2.id)
        user_b_id = max(match.user1.id, match.user2.id)
        
        try:
            ChatRoom.objects.get(user_a_id=user_a_id, user_b_id=user_b_id)
        except ChatRoom.DoesNotExist:
            missing_count += 1
            print(f"Missing ChatRoom for Match ID {match.id}: Users {user_a_id} ↔ {user_b_id}")
            
            # Create it
            chatroom, _ = ChatRoom.objects.get_or_create(
                user_a_id=user_a_id,
                user_b_id=user_b_id
            )
            created_count += 1
            print(f"  → Created ChatRoom ID {chatroom.id}\n")
    
    print(f"\n=== SUMMARY ===")
    print(f"Total Matches: {all_matches.count()}")
    print(f"Missing ChatRooms: {missing_count}")
    print(f"Created ChatRooms: {created_count}")

# Execute immediately when script is loaded into Django shell
print("\n=== CHATROOM CHECKER & CREATOR ===\n")

print("Checking for users 13 and 567...\n")
chatroom = check_chatroom(13, 567)

if not chatroom:
    print("\nAttempting to create ChatRoom...\n")
    chatroom = create_chatroom(13, 567)

# Fix all matches
print("\n" + "="*50)
print("\nFixing ALL matches without ChatRooms...\n")
fix_all_matches_without_chatrooms()

print("\n✓ Done!")
