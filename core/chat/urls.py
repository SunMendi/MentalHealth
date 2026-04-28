from django.urls import path 
from .views import (
    SessionListCreateAPIView, 
    MessageListCreateApiView, 
    DailyPlanAPIView, 
    ActivatePlanAPIView,
    CommunityPostAPIView
)


urlpatterns = [
    path('chat/sessions', SessionListCreateAPIView.as_view(), name='chat'),
    path('chat/sessions/<int:session_id>/messages', MessageListCreateApiView.as_view(), name='message'),
    path('plan/daily', DailyPlanAPIView.as_view(), name='daily-plan'),
    path('plan/activate/<int:category_id>', ActivatePlanAPIView.as_view(), name='activate-plan'),
    path('community/posts', CommunityPostAPIView.as_view(), name='community-posts'),
]
