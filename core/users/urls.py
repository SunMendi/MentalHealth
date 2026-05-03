from django.urls import path

from .views import GoogleAuthURLView, GoogleCallbackView, UserProfileView

urlpatterns = [
    path("google/auth-url/", GoogleAuthURLView.as_view(), name="google-auth-url"),
    path("google/callback/", GoogleCallbackView.as_view(), name="google-callback"),
    path("profile/", UserProfileView.as_view(), name="user-profile"),
    path("profile", UserProfileView.as_view()),
]
