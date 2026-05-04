import os
import uuid
import logging
from asgiref.sync import async_to_sync
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from .models import ChatSession, CommunityPost
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
from .services.plans import get_daily_task, complete_daily_task, activate_plan

logger = logging.getLogger("chat.views")


def _persist_temp_audio(audio_file):
    temp_name = f"input_{uuid.uuid4()}_{audio_file.name}"
    temp_dir = os.path.join(settings.BASE_DIR, "media", "temp")
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, temp_name)

    with open(temp_path, "wb+") as destination:
        for chunk in audio_file.chunks():
            destination.write(chunk)

    return temp_path


class AudioTranscriptionAPIView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        audio_file = request.FILES.get("audio")
        if not audio_file:
            return Response({"error": "Audio file is required."}, status=status.HTTP_400_BAD_REQUEST)

        temp_path = None
        try:
            temp_path = _persist_temp_audio(audio_file)
            transcription = transcribe_audio(temp_path)
            if not transcription:
                return Response(
                    {"error": "Could not transcribe audio. Please retry or type your message."},
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )

            return Response(
                {
                    "transcription": transcription,
                    "filename": audio_file.name,
                    "content_type": getattr(audio_file, "content_type", None),
                },
                status=status.HTTP_200_OK,
            )
        except Exception as exc:
            logger.exception("Audio transcription failed: %s", exc)
            return Response({"error": "Failed to transcribe audio."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception as cleanup_err:
                    logger.error("Failed to delete temp file %s: %s", temp_path, cleanup_err)


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
        logger.info("Session creation initiated | user_id=%s", request.user.id)
        serializer = CreateSessionSerializer(data=request.data)
        if not serializer.is_valid():
            logger.error("Session creation validation failed | errors=%s", serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            validated_data = dict(serializer.validated_data)
            # Ensure title is never None
            if validated_data.get("title") is None:
                validated_data["title"] = ""

            session = create_session({**validated_data, "user": request.user})
            logger.info("Session created successfully | session_id=%s", session.id)
            
            return Response(
                {
                    "id": session.id,
                    "title": session.title,
                    "status": session.status,
                    "created_at": session.created_at,
                },
                status=status.HTTP_201_CREATED,
            )
        except Exception as exc:
            logger.exception("Session creation failed: %s", exc)
            return Response({"error": "Failed to create session."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SessionDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, session_id):
        session = get_object_or_404(ChatSession, id=session_id, user=request.user)
        logger.info("Session deletion initiated | user_id=%s | session_id=%s", request.user.id, session.id)
        session.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MessageListCreateApiView(APIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, session_id):
        get_object_or_404(ChatSession, id=session_id, user=request.user)
        messages = get_all_messages_single_session(session_id)
        serializer = ChatMessageSerializer(messages, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, session_id):
        session = get_object_or_404(ChatSession, id=session_id, user=request.user)
        user_content = request.data.get("content", "")
        audio_file = request.FILES.get("audio")
        temp_path = None
        
        # 1. Handle audio upload and transcription
        if audio_file:
            try:
                temp_path = _persist_temp_audio(audio_file)

                # Transcribe for DB storage and context
                transcription = transcribe_audio(temp_path)
                if transcription:
                    user_content = transcription
            except Exception as e:
                logger.error("Error processing uploaded audio: %s", e)

        # 2. Check for empty input
        if not user_content and not audio_file:
            return Response({"error": "No content or audio provided"}, status=status.HTTP_400_BAD_REQUEST)

        # 3. Get AI Response and cleanup temp files
        try:
            assistant_message = handle_user_input(
                session_id=session.id,
                user_content=user_content
            )
            
            # 4. Generate AI Voice (TTS) - FILE-LESS BASE64
            audio_base64 = None
            try:
                tts_res = async_to_sync(generate_speech_base64)(assistant_message.content)
                if tts_res:
                    audio_base64 = tts_res["base64"]
                    # Update metadata with voice info
                    metadata = dict(assistant_message.metadata or {})
                    metadata.update({"tts_voice": tts_res["voice"]})
                    assistant_message.metadata = metadata
                    assistant_message.save(update_fields=["metadata"])
            except Exception as exc:
                logger.exception("Assistant voice generation failed | message_id=%s", assistant_message.id)

            # 5. Fetch full conversation pair for response
            messages = get_all_messages_single_session(session.id)
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

        except Exception as exc:
            logger.exception("Message processing failed: %s", exc)
            return Response({"error": "Failed to process message."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            # Absolute cleanup of temp audio
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception as cleanup_err:
                    logger.error("Failed to delete temp file %s: %s", temp_path, cleanup_err)


class DailyPlanAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        data = get_daily_task(request.user)
        if not data or not data.get("task"):
            return Response({"message": "No active plan or task found for today."}, status=status.HTTP_404_NOT_FOUND)
        
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
        try:
            plan = activate_plan(request.user, category_id)
            return Response({"message": f"Plan for category {category_id} activated.", "plan_id": plan.id})
        except Exception as e:
            logger.exception("Plan activation failed: %s", e)
            return Response({"error": "Could not activate plan."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CommunityPostAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        posts = CommunityPost.objects.all()[:50]
        serializer = CommunityPostSerializer(posts, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = CommunityPostSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        CommunityPost.objects.create(content=serializer.validated_data["content"])
        return Response({"message": "Thought shared anonymously."}, status=status.HTTP_201_CREATED)
