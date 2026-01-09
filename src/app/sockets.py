#gog\src\app\sockets.py
from flask import session
from flask_socketio import emit, join_room, leave_room
from flask_login import current_user
from . import socketio, db
from .models import Message, Conversation, User
from datetime import datetime


@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    if current_user.is_authenticated:
        # Join user's personal room for notifications
        join_room(f'user_{current_user.id}')
        
        # Check for admin status
        is_admin_user = getattr(current_user, 'is_admin', False)
        is_admin_session = session.get('is_admin')

        # DEBUG PRINT - Check your server console when you refresh the Admin Inbox
        print(f"User connected: {current_user.id}. Is Admin User: {is_admin_user}, Is Admin Session: {is_admin_session}")

        if is_admin_user or is_admin_session:
            join_room('admins')
            print(f"User {current_user.id} joined 'admins' room")


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    if current_user.is_authenticated:
        leave_room(f'user_{current_user.id}')
        if current_user.is_admin:
            leave_room('admins')


@socketio.on('join_conversation')
def handle_join_conversation(data):
    """Join a specific conversation room"""
    conversation_id = data.get('conversation_id')
    if conversation_id:
        join_room(f'conversation_{conversation_id}')


@socketio.on('leave_conversation')
def handle_leave_conversation(data):
    """Leave a specific conversation room"""
    conversation_id = data.get('conversation_id')
    if conversation_id:
        leave_room(f'conversation_{conversation_id}')


@socketio.on('send_message')
def handle_send_message(data):
    """Handle sending a message via WebSocket"""
    if not current_user.is_authenticated:
        return

    content = data.get('content', '').strip()
    conversation_id = data.get('conversation_id')

    if not content or not conversation_id:
        return

    conversation = Conversation.query.get(conversation_id)
    if not conversation:
        return

    # Check permissions and determine if message is from admin
    is_admin = getattr(current_user, 'is_admin', False) or session.get('is_admin')
    if not is_admin and conversation.user_id != current_user.id:
        return

    # Determine if this is actually an admin sending a message
    # Only mark as from_admin if they're in an admin session
    is_from_admin = session.get('is_admin', False)

    print(f"User {current_user.id} sending message: is_admin={is_admin}, is_from_admin={is_from_admin}, session.is_admin={session.get('is_admin')}")

    # Create Message
    message = Message(
        conversation_id=conversation.id,
        sender_id=current_user.id,
        content=content,
        is_from_admin=is_from_admin,
        is_read=False
    )
    db.session.add(message)
    conversation.updated_at = datetime.utcnow()
    db.session.commit()

    # Emit to the chat window (conversation room)
    emit('new_message', {
        'id': message.id,
        'content': message.content,
        'sender_name': current_user.username,
        'is_from_admin': message.is_from_admin,
        'created_at': message.created_at.strftime('%d.%m.%Y %H:%M'),
        'conversation_id': conversation.id
    }, room=f'conversation_{conversation_id}')

    # --- NOTIFICATION LOGIC (The Webhook part) ---
    if is_from_admin:
        # Admin sent message -> Notify the specific User
        emit('notification', {
            'type': 'new_message',
            'count': 1,
            'conversation_id': conversation.id,
            'content': message.content,
            'from': current_user.username,
            'timestamp': datetime.utcnow().strftime('%d.%m.%Y %H:%M')
        }, room=f'user_{conversation.user_id}')
    else:
        # User sent message -> Notify ALL Admins
        emit('notification', {
            'type': 'new_message',
            'conversation_id': conversation.id,
            'content': message.content,
            'from': current_user.username,
            'timestamp': datetime.utcnow().strftime('%d.%m.%Y %H:%M')
        }, room='admins')

@socketio.on('mark_read')
def handle_mark_read(data):
    """Mark messages as read"""
    if not current_user.is_authenticated:
        return

    conversation_id = data.get('conversation_id')
    if not conversation_id:
        return

    conversation = Conversation.query.get(conversation_id)
    if not conversation:
        return

    # Mark appropriate messages as read
    is_admin = getattr(current_user, 'is_admin', False) or session.get('is_admin')
    if is_admin:
        # Admin reads user messages
        messages = Message.query.filter_by(
            conversation_id=conversation_id,
            is_from_admin=False,
            is_read=False
        ).all()
        print(f"Admin marking {len(messages)} messages as read in conversation {conversation_id}")
    else:
        # User reads admin messages
        if conversation.user_id != current_user.id:
            return
        messages = Message.query.filter_by(
            conversation_id=conversation_id,
            is_from_admin=True,
            is_read=False
        ).all()

    for msg in messages:
        msg.is_read = True
    db.session.commit()
