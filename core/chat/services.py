from django.shortcuts import get_object_or_404

from .models import ChatMessage, ChatSession


def create_session(dictdata):
    return ChatSession.objects.create(**dictdata)


def get_all_messages_single_session(session_id):
    return ChatMessage.objects.filter(session_id=session_id).order_by("created_at")


def create_user_message(session_id, content):
    session = get_object_or_404(ChatSession, id=session_id)
    return ChatMessage.objects.create(
        session=session,
        sender="user",
        content=content,
        message_type="text",
    )


def create_assistant_message(session_id, content):
    session = get_object_or_404(ChatSession, id=session_id)
    return ChatMessage.objects.create(
        session=session,
        sender="assistant",
        content=content,
        message_type="text",
    )
