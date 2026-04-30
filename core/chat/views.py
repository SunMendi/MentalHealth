import os
import uuid
from django.conf import settings
from asgiref.sync import async_to_sync
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
from .services.voice import transcribe_audio, generate_speech


class SessionListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = CreateSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session = create_session({**serializer.validated_data, "user": request.user})

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
        if audio_file:
            audio_name = f"resp_{assistant_message.id}.mp3"
            audio_dir = os.path.join(settings.BASE_DIR, "media", "responses")
            os.makedirs(audio_dir, exist_ok=True)
            audio_path = os.path.join(audio_dir, audio_name)
            
            async_to_sync(generate_speech)(assistant_message.content, audio_path)
            audio_url = f"/media/responses/{audio_name}"

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
