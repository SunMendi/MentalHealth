import os
import uuid
from django.conf import settings
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from .models import CommunityPost
from .serializers import (
    ChatMessageSerializer,
    CreateMessageSerializer,
    CreateSessionSerializer,
    CommunityPostSerializer,
)
from .services.chat_services import (
    create_session,
    get_all_messages_single_session,
)
from .services.brain import handle_user_input
from .services.plans import get_daily_task, complete_daily_task, activate_plan
from .services.voice import generate_and_upload_speech, transcribe_audio


import logging

logger = logging.getLogger("chat.views")


def attach_assistant_audio(assistant_message):
    if assistant_message.sender != "assistant" or not assistant_message.content:
        return None

    tts_payload = generate_and_upload_speech(
        text=assistant_message.content,
        public_id=f"assistant_message_{assistant_message.id}",
    )
    metadata = dict(assistant_message.metadata or {})
    metadata.update(
        {
            "audio_url": tts_payload["audio_url"],
            "tts_voice": tts_payload["voice"],
        }
    )
    assistant_message.metadata = metadata
    assistant_message.save(update_fields=["metadata"])
    return tts_payload["audio_url"]

class SessionListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        sessions = (
            request.user.chat_sessions
            .all()
            .order_by("-updated_at", "-created_at")
        )
        return Response(
            [
                {
                    "id": session.id,
                    "title": session.title,
                    "status": session.status,
                    "created_at": session.created_at,
                }
                for session in sessions
            ],
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        logger.info("Session creation initiated | user_id=%s | data=%s", request.user.id, request.data)
        serializer = CreateSessionSerializer(data=request.data)
        if not serializer.is_valid():
            logger.error("Session creation validation failed | errors=%s", serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            validated_data = dict(serializer.validated_data)
            if validated_data.get("title") is None:
                validated_data["title"] = ""

            session = create_session({**validated_data, "user": request.user})
            logger.info("Session created successfully | session_id=%s", session.id)
        except Exception as exc:
            logger.exception("Session creation failed in service: %s", exc)
            return Response({"error": "Internal server error during session creation"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(
            {
                "id": session.id,
                "title": session.title,
                "status": session.status,
                "created_at": session.created_at,
            },
            status=status.HTTP_201_CREATED,
        )


class MessageListCreateApiView(APIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, session_id):
        messages = get_all_messages_single_session(session_id)
        serializer = ChatMessageSerializer(messages, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, session_id):
        user_content = request.data.get("content")
        audio_file = request.FILES.get("audio")
        
        if audio_file:
            temp_name = f"temp_{uuid.uuid4()}.wav"
            temp_path = os.path.join(settings.BASE_DIR, "media", "temp", temp_name)
            os.makedirs(os.path.dirname(temp_path), exist_ok=True)
            
            with open(temp_path, 'wb+') as destination:
                for chunk in audio_file.chunks():
                    destination.write(chunk)
            
            user_content = transcribe_audio(temp_path)
            os.remove(temp_path)
            
            if not user_content:
                return Response({"error": "Could not transcribe audio"}, status=status.HTTP_400_BAD_REQUEST)

        if not user_content:
            return Response({"error": "No content or audio provided"}, status=status.HTTP_400_BAD_REQUEST)

        assistant_message = handle_user_input(
            session_id=session_id,
            user_content=user_content,
        )
        audio_url = None
        try:
            audio_url = attach_assistant_audio(assistant_message)
        except Exception as exc:
            logger.exception(
                "Assistant audio generation failed | message_id=%s | error=%s",
                assistant_message.id,
                exc,
            )

        messages = get_all_messages_single_session(session_id)
        user_message = messages.filter(sender="user").last()

        return Response(
            {
                "user_message": ChatMessageSerializer(user_message).data,
                "assistant_message": ChatMessageSerializer(assistant_message).data,
                "audio_url": audio_url,
                "transcription": user_content if audio_file else None
            },
            status=status.HTTP_201_CREATED,
        )


class DailyPlanAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        data = get_daily_task(request.user)
        if not data:
            return Response({"message": "No active plan found."}, status=status.HTTP_404_NOT_FOUND)
        
        return Response({
            "day": data["day"],
            "title": data["task"].title,
            "description": data["task"].description,
            "is_completed": data["is_completed"]
        })

    def post(self, request):
        success = complete_daily_task(request.user)
        if success:
            return Response({"message": "Task completed!"})
        return Response({"error": "Failed to complete task."}, status=status.HTTP_400_BAD_REQUEST)


class ActivatePlanAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, category_id):
        plan = activate_plan(request.user, category_id)
        return Response({"message": f"Plan for category {category_id} activated.", "plan_id": plan.id})


class CommunityPostAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        posts = CommunityPost.objects.all()[:50]
        serializer = CommunityPostSerializer(posts, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = CommunityPostSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        CommunityPost.objects.create(content=serializer.validated_data["content"])
        return Response({"message": "Thought shared anonymously."}, status=status.HTTP_201_CREATED)
