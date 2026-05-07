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
from .models import AppVersionConfig
from .serializers import (
    AppVersionCheckSerializer,
    AppVersionConfigSerializer,
    ChatMessageSerializer,
    CreateMessageSerializer,
    CreateSessionSerializer,
    TextToSpeechSerializer,
    CommunityPostSerializer,
)
from .services.chat_services import (
    create_session,
    get_all_messages_single_session,
)
from .services.brain import handle_user_input
from .services.voice import generate_speech_base64, transcribe_audio
from .services.plans import get_daily_task, complete_daily_task, activate_plan
from .audio_utils import get_audio_duration_seconds
from .throttles import AudioTranscriptionRateThrottle, ChatMessageRateThrottle

logger = logging.getLogger("chat.views")
MAX_AUDIO_DURATION_SECONDS = int(os.getenv("MAX_AUDIO_DURATION_SECONDS", "180"))


def _persist_temp_audio(audio_file):
    temp_name = f"input_{uuid.uuid4()}_{audio_file.name}"
    temp_dir = os.path.join(settings.BASE_DIR, "media", "temp")
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, temp_name)

    with open(temp_path, "wb+") as destination:
        for chunk in audio_file.chunks():
            destination.write(chunk)

    return temp_path


def _parse_version_parts(version: str):
    parts = [int(part) for part in str(version).split(".")]
    parts.extend([0] * (3 - len(parts)))
    return tuple(parts[:3])


class AudioTranscriptionAPIView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [permissions.IsAuthenticated]

    def get_throttles(self):
        if self.request.method == "POST":
            return [AudioTranscriptionRateThrottle()]
        return super().get_throttles()

    def post(self, request):
        audio_file = request.FILES.get("audio")
        if not audio_file:
            return Response({"error": "Audio file is required."}, status=status.HTTP_400_BAD_REQUEST)

        temp_path = None
        try:
            temp_path = _persist_temp_audio(audio_file)
            duration_seconds = get_audio_duration_seconds(temp_path)
            if duration_seconds is None:
                return Response(
                    {"error": "Could not verify audio duration. Please upload a supported audio file."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if duration_seconds > MAX_AUDIO_DURATION_SECONDS:
                return Response(
                    {
                        "error": (
                            f"Audio is too long. Maximum allowed length is "
                            f"{MAX_AUDIO_DURATION_SECONDS // 60} minutes."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

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


class TextToSpeechAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = TextToSpeechSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            tts_res = async_to_sync(generate_speech_base64)(serializer.validated_data["text"])
            if not tts_res:
                return Response(
                    {"error": "Could not generate audio right now. Please try again."},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

            return Response(
                {
                    "audio_base64": tts_res["base64"],
                    "voice": tts_res["voice"],
                },
                status=status.HTTP_200_OK,
            )
        except Exception as exc:
            logger.exception("Standalone TTS generation failed: %s", exc)
            return Response({"error": "Failed to generate speech."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AppVersionCheckAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        serializer = AppVersionCheckSerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        platform = serializer.validated_data["platform"]
        version = serializer.validated_data["version"]
        config = AppVersionConfig.objects.filter(platform=platform).first()
        if not config:
            return Response(
                {"error": f"No app version configuration found for platform '{platform}'."},
                status=status.HTTP_404_NOT_FOUND,
            )

        current_parts = _parse_version_parts(version)
        latest_parts = _parse_version_parts(config.latest_version)
        minimum_parts = _parse_version_parts(config.minimum_supported_version)
        update_required = current_parts < minimum_parts or config.force_update
        update_available = current_parts < latest_parts

        return Response(
            {
                "platform": config.platform,
                "current_version": version,
                "latest_version": config.latest_version,
                "minimum_supported_version": config.minimum_supported_version,
                "update_required": update_required,
                "update_available": update_available,
                "force_update": config.force_update,
                "update_message": config.update_message,
                "store_url": config.store_url,
            },
            status=status.HTTP_200_OK,
        )


class AppVersionConfigAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not request.user.is_staff:
            return Response({"error": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

        platform = (request.query_params.get("platform") or "").strip().lower()
        if platform:
            config = get_object_or_404(AppVersionConfig, platform=platform)
            return Response(
                {
                    "platform": config.platform,
                    "latest_version": config.latest_version,
                    "minimum_supported_version": config.minimum_supported_version,
                    "force_update": config.force_update,
                    "update_message": config.update_message,
                    "store_url": config.store_url,
                }
            )

        configs = AppVersionConfig.objects.all()
        return Response(
            [
                {
                    "platform": config.platform,
                    "latest_version": config.latest_version,
                    "minimum_supported_version": config.minimum_supported_version,
                    "force_update": config.force_update,
                    "update_message": config.update_message,
                    "store_url": config.store_url,
                }
                for config in configs
            ]
        )

    def post(self, request):
        if not request.user.is_staff:
            return Response({"error": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

        serializer = AppVersionConfigSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        config, _created = AppVersionConfig.objects.update_or_create(
            platform=serializer.validated_data["platform"],
            defaults={
                "latest_version": serializer.validated_data["latest_version"],
                "minimum_supported_version": serializer.validated_data["minimum_supported_version"],
                "force_update": serializer.validated_data["force_update"],
                "update_message": serializer.validated_data["update_message"],
                "store_url": serializer.validated_data["store_url"],
            },
        )

        return Response(
            {
                "platform": config.platform,
                "latest_version": config.latest_version,
                "minimum_supported_version": config.minimum_supported_version,
                "force_update": config.force_update,
                "update_message": config.update_message,
                "store_url": config.store_url,
            },
            status=status.HTTP_200_OK,
        )


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

    def get_throttles(self):
        if self.request.method == "POST":
            return [ChatMessageRateThrottle()]
        return super().get_throttles()

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
                duration_seconds = get_audio_duration_seconds(temp_path)
                if duration_seconds is None:
                    return Response(
                        {"error": "Could not verify audio duration. Please upload a supported audio file."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                if duration_seconds > MAX_AUDIO_DURATION_SECONDS:
                    return Response(
                        {
                            "error": (
                                f"Audio is too long. Maximum allowed length is "
                                f"{MAX_AUDIO_DURATION_SECONDS // 60} minutes."
                            )
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

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
