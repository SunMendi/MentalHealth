import os
import uuid
import logging
from asgiref.sync import async_to_sync
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
from .services.voice import generate_speech_base64, transcribe_audio

logger = logging.getLogger("chat.views")

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
        user_content = request.data.get("content", "")
        audio_file = request.FILES.get("audio")
        temp_path = None
        
        # 1. Handle audio upload if present
        if audio_file:
            temp_name = f"input_{uuid.uuid4()}_{audio_file.name}"
            temp_path = os.path.join(settings.BASE_DIR, "media", "temp", temp_name)
            os.makedirs(os.path.dirname(temp_path), exist_ok=True)
            
            with open(temp_path, 'wb+') as destination:
                for chunk in audio_file.chunks():
                    destination.write(chunk)
            
            # Use Groq Whisper for quick transcription to text for DB storage
            # But we pass the raw audio to Gemini for better linguistic analysis
            user_content = transcribe_audio(temp_path) or user_content

        if not user_content and not audio_file:
            return Response({"error": "No content or audio provided"}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Get AI Response (Pass audio_path for Gemini's native hearing)
        try:
            assistant_message = handle_user_input(
                session_id=session_id,
                user_content=user_content,
                audio_path=temp_path
            )
        finally:
            # Cleanup temp audio immediately
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
        
        # 3. Generate AI Voice (TTS) - FILE-LESS BASE64
        audio_base64 = None
        try:
            tts_res = async_to_sync(generate_speech_base64)(assistant_message.content)
            if tts_res:
                audio_base64 = tts_res["base64"]
                metadata = dict(assistant_message.metadata or {})
                metadata.update({"tts_voice": tts_res["voice"]})
                assistant_message.metadata = metadata
                assistant_message.save(update_fields=["metadata"])
        except Exception as exc:
            logger.exception("Assistant voice generation failed | message_id=%s", assistant_message.id)

        messages = get_all_messages_single_session(session_id)
        user_message = messages.filter(sender="user").last()

        return Response(
            {
                "user_message": ChatMessageSerializer(user_message).data,
                "assistant_message": ChatMessageSerializer(assistant_message).data,
                "audio_base64": audio_base64,
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
