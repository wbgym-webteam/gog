# Messaging System Documentation

## Overview

The messaging system allows bidirectional communication between regular users and the admin team. Both users and admins can initiate conversations. All admins share a unified inbox where they can view and respond to user messages. Regular users cannot message each other - they can only communicate with admins.

**Real-time messaging** is enabled via WebSockets (Flask-SocketIO), so messages appear instantly without page refresh - similar to WhatsApp or Discord.

## Dependencies

The messaging system requires:
- `flask-socketio` - WebSocket support for Flask

Install with:
```bash
pip install flask-socketio
```

## Architecture

### Database Models

The messaging system uses two database tables:

#### Conversations Table
Each user has exactly one conversation with the admin team.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| user_id | INTEGER | Foreign key to users table (unique per user) |
| created_at | DATETIME | When the conversation was started |
| updated_at | DATETIME | Last activity timestamp |

#### Messages Table
Individual messages within a conversation.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| conversation_id | INTEGER | Foreign key to conversations table |
| sender_id | INTEGER | Foreign key to users table (who sent the message) |
| content | TEXT | The message content |
| is_from_admin | BOOLEAN | True if sent by an admin, False if sent by user |
| is_read | BOOLEAN | Whether the message has been read by the recipient |
| created_at | DATETIME | When the message was sent |

### Models (src/app/models.py)

```python
class Conversation(db.Model):
    # One conversation per user with the admin team
    # Relationship: user (User), messages (list of Message)

class Message(db.Model):
    # Individual message within a conversation
    # Relationship: conversation (Conversation), sender (User)
```

## User Interface

### For Regular Users

**Access:** Dashboard -> "Admin kontaktieren" button

**Route:** `/gog/messages`

**Features:**
- View conversation history with admins
- Send new messages to the admin team
- Messages appear in a chat-style interface
- User messages are displayed on the right (purple)
- Admin responses are displayed on the left (gray)
- Timestamps shown for each message
- **Unread notification badge** on "Admin kontaktieren" button when admin has sent new messages

### For Admins

**Access:** Admin Dashboard -> "Nachrichten" button

**Routes:**
- `/gog/admin/messages` - Inbox (list of all conversations)
- `/gog/admin/messages/<conversation_id>` - Individual conversation view
- `/gog/admin/messages/new` - Start new conversation with a user

**Features:**
- View all user conversations in a unified inbox
- Unread message count badge on dashboard button
- Per-conversation unread count in inbox
- Conversations sorted by last activity (most recent first)
- Reply to users directly from conversation view
- Messages marked as read when conversation is viewed
- **Initiate new conversations** with any user via "Neue Nachricht" button
- User selection dropdown showing users with/without existing conversations

## Routes

### User Routes (src/app/gog_views.py)

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/gog/messages` | View user's conversation with admins |
| POST | `/gog/messages` | Send a new message to admins |

### Admin Routes (src/app/admin_views.py)

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/gog/admin/messages` | View all conversations (inbox) |
| GET | `/gog/admin/messages/new` | Show user selection form for new conversation |
| POST | `/gog/admin/messages/new` | Create/open conversation and send message |
| GET | `/gog/admin/messages/<id>` | View specific conversation |
| POST | `/gog/admin/messages/<id>` | Reply to a conversation |

## Read Status Logic

### When a user views their conversation:
- All admin messages (`is_from_admin=True`) in that conversation are marked as read

### When an admin views a conversation:
- All user messages (`is_from_admin=False`) in that conversation are marked as read

### Unread count calculation:
- **User dashboard badge:** Count of messages in user's conversation where `is_from_admin=True` AND `is_read=False`
- **Admin dashboard badge:** Count of all messages where `is_from_admin=False` AND `is_read=False`
- **Per-conversation count (admin inbox):** Same filter but limited to specific conversation

## Templates

| File | Purpose |
|------|---------|
| `templates/gog/gog_messages.html` | User messaging page (with Socket.IO) |
| `templates/gog/admin/messages_inbox.html` | Admin inbox listing all conversations |
| `templates/gog/admin/messages_conversation.html` | Admin view of single conversation (with Socket.IO) |
| `templates/gog/admin/messages_new.html` | Admin form to start new conversation |

### Backend Files

| File | Purpose |
|------|---------|
| `src/app/sockets.py` | WebSocket event handlers |
| `src/app/__init__.py` | SocketIO initialization |
| `src/main.py` | App runner with `socketio.run()` |

## Real-Time Messaging (WebSockets)

The messaging system uses Flask-SocketIO for real-time communication. Messages appear instantly without page refresh.

### Technology Stack
- **Backend:** Flask-SocketIO (WebSocket server)
- **Frontend:** Socket.IO client library (CDN)
- **Transport:** WebSocket with fallback to long-polling

### Socket Events (src/app/sockets.py)

| Event | Direction | Description |
|-------|-----------|-------------|
| `connect` | Client → Server | User connects, joins personal room and admin room (if admin) |
| `disconnect` | Client → Server | User disconnects, leaves rooms |
| `join_conversation` | Client → Server | Join a specific conversation room |
| `leave_conversation` | Client → Server | Leave a conversation room |
| `send_message` | Client → Server | Send a new message |
| `new_message` | Server → Client | Broadcast new message to conversation room |
| `notification` | Server → Client | Notify recipient of new message |
| `mark_read` | Client → Server | Mark messages as read |

### Room Structure
- `user_{id}` - Personal room for each user (for notifications)
- `admins` - Shared room for all admin users
- `conversation_{id}` - Room for each active conversation

### Connection Status
Both user and admin interfaces show a connection status indicator:
- **Green "Verbunden"** - Connected to WebSocket server
- **Red "Verbindung unterbrochen"** - Disconnected, send button disabled

### How It Works
1. User opens messaging page → connects to Socket.IO → joins conversation room
2. User types message → emits `send_message` event
3. Server saves message to database → emits `new_message` to conversation room
4. Server emits `notification` to recipient's personal room (or admin room)
5. All clients in conversation room receive message instantly
6. Message appears in chat without page refresh

## Security

- User routes protected by `@login_required` and `@regular_user_required` decorators
- Admin routes protected by `@login_required` and `@admin_required` decorators
- Users can only access their own conversation
- Admins can access all conversations
- Messages are sanitized through form handling
- WebSocket events validate user authentication and authorization

## Example Flow

1. **User sends message (real-time):**
   - User clicks "Admin kontaktieren" on dashboard
   - WebSocket connection established, status shows "Verbunden"
   - If no conversation exists, one is created automatically
   - User types message and clicks "Senden"
   - Message sent via WebSocket (`send_message` event)
   - Server saves message and broadcasts to conversation room
   - Message appears instantly in chat (no page refresh)
   - Admin receives notification if viewing inbox

2. **Admin receives and replies (real-time):**
   - Admin has messaging page open
   - New message appears instantly via WebSocket
   - Admin types reply and clicks "Senden"
   - Reply sent via WebSocket
   - User sees reply instantly (if on messaging page)
   - If user is on dashboard, unread badge updates on next visit

3. **Real-time conversation:**
   - Both user and admin have messaging page open
   - Messages appear instantly for both parties
   - No page refresh needed
   - Connection status indicator shows live status

4. **Admin initiates conversation:**
   - Admin clicks "Nachrichten" on dashboard
   - Admin clicks "Neue Nachricht" button
   - Admin selects a user from dropdown (grouped by new/existing conversations)
   - Admin types optional message
   - Admin clicks "Nachricht senden"
   - If user has no conversation, one is created
   - Admin is redirected to the conversation view
   - User sees notification badge on dashboard
