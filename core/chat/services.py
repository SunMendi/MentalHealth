from django.shortcuts import get_object_or_404

from .models import ChatMessage, ChatSession

from django.db import IntegrityError 

from rest_framework.exceptions import ValidationError 

import logging 

logger= logging.getLogger(__name__)


def create_session(validated_data: dict) -> ChatSession:
    try:
        session = ChatSession.objects.create(**validated_data)
        return session 
    except IntegrityError as e:
        error = str(e).lower() 
        logger.warning("Session creation conflict: %s | data=%s", e, validated_data)
        
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
