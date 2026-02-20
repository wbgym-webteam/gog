#gog\src\app\sockets.py
from flask import session
from flask_socketio import emit, join_room, leave_room
from flask_login import current_user
from . import socketio, db
from .models import Admin, Message, Conversation, User
from datetime import datetime


def _is_admin_user():
    """Return True if the currently logged-in user is an Admin instance."""
    return isinstance(current_user, Admin) or bool(session.get('is_admin'))


@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    if current_user.is_authenticated:
        join_room(f'user_{current_user.id}')

        is_admin = _is_admin_user()
        print(f"User connected: {current_user.id}. Is Admin: {is_admin}")

        if is_admin:
            join_room('admins')
            print(f"User {current_user.id} joined 'admins' room")


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    if current_user.is_authenticated:
        leave_room(f'user_{current_user.id}')
        if _is_admin_user():
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

    is_admin = _is_admin_user()

    # Permission check: admins can message any conversation; users only their own
    if not is_admin and conversation.user_id != current_user.id:
        return

    is_from_admin = is_admin

    print(f"User {current_user.id} sending message: is_admin={is_admin}, is_from_admin={is_from_admin}")

    message = Message(
        conversation_id=conversation.id,
        # Set the correct sender FK depending on who is sending
        admin_sender_id=current_user.id if is_from_admin else None,
        sender_id=None if is_from_admin else current_user.id,
        content=content,
        is_from_admin=is_from_admin,
        is_read=False
    )
    db.session.add(message)
    conversation.updated_at = datetime.utcnow()
    db.session.commit()

    emit('new_message', {
        'id': message.id,
        'content': message.content,
        'sender_name': current_user.username,
        'is_from_admin': message.is_from_admin,
        'created_at': message.created_at.strftime('%d.%m.%Y %H:%M'),
        'conversation_id': conversation.id
    }, room=f'conversation_{conversation_id}')

    if is_from_admin:
        emit('notification', {
            'type': 'new_message',
            'count': 1,
            'conversation_id': conversation.id,
            'content': message.content,
            'from': current_user.username,
            'timestamp': datetime.utcnow().strftime('%d.%m.%Y %H:%M')
        }, room=f'user_{conversation.user_id}')
    else:
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

    is_admin = _is_admin_user()
    if is_admin:
        messages = Message.query.filter_by(
            conversation_id=conversation_id,
            is_from_admin=False,
            is_read=False
        ).all()
        print(f"Admin marking {len(messages)} messages as read in conversation {conversation_id}")
    else:
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
