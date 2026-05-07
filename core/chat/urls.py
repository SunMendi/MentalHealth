from django.urls import path 
from .views import (
    AppVersionCheckAPIView,
    AppVersionConfigAPIView,
    AudioTranscriptionAPIView,
    TextToSpeechAPIView,
    SessionListCreateAPIView, 
    SessionDetailAPIView,
    MessageListCreateApiView, 
    DailyPlanAPIView, 
    ActivatePlanAPIView,
    CommunityPostAPIView
)


urlpatterns = [
    path('app/version-check/', AppVersionCheckAPIView.as_view(), name='app-version-check'),
    path('app/version-check', AppVersionCheckAPIView.as_view()),
    path('app/version-config/', AppVersionConfigAPIView.as_view(), name='app-version-config'),
    path('app/version-config', AppVersionConfigAPIView.as_view()),
    path('voice/transcribe/', AudioTranscriptionAPIView.as_view(), name='voice-transcribe'),
    path('voice/transcribe', AudioTranscriptionAPIView.as_view()),
    path('voice/tts/', TextToSpeechAPIView.as_view(), name='voice-tts'),
    path('voice/tts', TextToSpeechAPIView.as_view()),
    path('chat/sessions/', SessionListCreateAPIView.as_view(), name='chat'),
    path('chat/sessions', SessionListCreateAPIView.as_view()),
    path('chat/sessions/<int:session_id>/', SessionDetailAPIView.as_view(), name='session-detail'),
    path('chat/sessions/<int:session_id>', SessionDetailAPIView.as_view()),
    path('chat/sessions/<int:session_id>/messages/', MessageListCreateApiView.as_view(), name='message'),
    path('chat/sessions/<int:session_id>/messages', MessageListCreateApiView.as_view()),
    path('plan/daily/', DailyPlanAPIView.as_view(), name='daily-plan'),
    path('plan/daily', DailyPlanAPIView.as_view()),
    path('plan/activate/<int:category_id>/', ActivatePlanAPIView.as_view(), name='activate-plan'),
    path('plan/activate/<int:category_id>', ActivatePlanAPIView.as_view()),
    path('community/posts/', CommunityPostAPIView.as_view(), name='community-posts'),
    path('community/posts', CommunityPostAPIView.as_view()),
]
