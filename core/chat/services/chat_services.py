import logging
from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from ..models import ChatMessage, ChatSession

logger = logging.getLogger(__name__)

def create_session(dictdata):
    # Map 'problem_category' (ID) to 'problem_category_id' if present
    category_id = dictdata.pop('problem_category', None)
    if category_id:
        dictdata['problem_category_id'] = category_id

    try:
        return ChatSession.objects.create(**dictdata)
    except IntegrityError as e:
        error = str(e).lower()
        logger.warning("Session creation conflict: %s | data=%s", e, dictdata)
        
        if 'name' in error or 'title' in error:
            raise ValidationError({'title': 'A session with this title already exists.'})
        
        if 'foreign key' in error:
            raise ValidationError({'detail': 'Referenced user or category does not exist.'})
            
        raise ValidationError({'detail': 'A database conflict occurred while creating the session.'})

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
