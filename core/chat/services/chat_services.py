from django.shortcuts import get_object_or_404
from ..models import ChatMessage, ChatSession

def create_session(dictdata):
    # Map 'problem_category' (ID) to 'problem_category_id' if present
    category_id = dictdata.pop('problem_category', None)
    if category_id:
        dictdata['problem_category_id'] = category_id
    return ChatSession.objects.create(**dictdata)

def get_all_messages_single_session(session_id):
    return ChatMessage.objects.filter(session_id=session_id).order_by("created_at")

def create_user_message(session_id, content):
    session = get_object_or_404(ChatSession, id=session_id)
    return ChatMessage.objects.create(
        session=session,
        sender="user",
        content=content,
    )

def create_assistant_message(session_id, content, suggested_replies=None, metadata=None):
    session = get_object_or_404(ChatSession, id=session_id)
    return ChatMessage.objects.create(
        session=session,
        sender="assistant",
        content=content,
        suggested_replies=suggested_replies or [],
        metadata=metadata or {},
    )
