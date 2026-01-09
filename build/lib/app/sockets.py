#gog\build\lib\app\sockets.py
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

        # If admin, join admin room to receive all messages
        if current_user.is_admin:
            join_room('admins')


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

    # Security check: user can only send to their own conversation
    # Admin can send to any conversation
    if not current_user.is_admin and conversation.user_id != current_user.id:
        return

    # Create and save the message
    message = Message(
        conversation_id=conversation.id,
        sender_id=current_user.id,
        content=content,
        is_from_admin=current_user.is_admin,
        is_read=False
    )
    db.session.add(message)
    conversation.updated_at = datetime.utcnow()
    db.session.commit()

    # Prepare message data for broadcast
    message_data = {
        'id': message.id,
        'content': message.content,
        'sender_id': message.sender_id,
        'sender_name': current_user.username,
        'is_from_admin': message.is_from_admin,
        'created_at': message.created_at.strftime('%d.%m.%Y %H:%M'),
        'conversation_id': conversation.id
    }

    # Emit to conversation room (everyone viewing this conversation)
    emit('new_message', message_data, room=f'conversation_{conversation_id}')

    # Notify the recipient
    if current_user.is_admin:
        # Notify the user
        emit('notification', {
            'type': 'new_message',
            'conversation_id': conversation.id,
            'from': current_user.username
        }, room=f'user_{conversation.user_id}')
    else:
        # Notify all admins
        emit('notification', {
            'type': 'new_message',
            'conversation_id': conversation.id,
            'from': current_user.username,
            'user_id': current_user.id
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
    if current_user.is_admin:
        # Admin reads user messages
        messages = Message.query.filter_by(
            conversation_id=conversation_id,
            is_from_admin=False,
            is_read=False
        ).all()
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
