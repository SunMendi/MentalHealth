import os
import secrets
import requests
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_exempt
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

@method_decorator(xframe_options_exempt, name="dispatch")
class GoogleAuthURLView(APIView):
    # Allow anyone to access this to get the URL
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        google_client_id = os.getenv("GOOGLE_CLIENT_ID")
        # Ensure we use HTTPS for the redirect_uri in production
        redirect_uri = os.getenv("GOOGLE_REDIRECT_URI") or request.build_absolute_uri(
            reverse("google-callback")
        ).replace("http://", "https://")

        if not google_client_id:
            return Response({"error": "GOOGLE_CLIENT_ID missing"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        state = secrets.token_urlsafe(32)
        params = {
            "client_id": google_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "online",
            "prompt": "select_account",
        }

        auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
        return Response({"auth_url": auth_url})

@method_decorator(xframe_options_exempt, name="dispatch")
class GoogleCallbackView(APIView):
    # CRITICAL: Disable all authentication and permissions for the callback
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        print(">>> GOOGLE CALLBACK INITIATED")
        code = request.GET.get("code")
        
        if not code:
            return Response({"error": "No code provided by Google"}, status=status.HTTP_400_BAD_REQUEST)

        google_client_id = os.getenv("GOOGLE_CLIENT_ID")
        google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        redirect_uri = os.getenv("GOOGLE_REDIRECT_URI") or request.build_absolute_uri(
            reverse("google-callback")
        ).replace("http://", "https://")

        print(f">>> Exchanging code with redirect_uri: {redirect_uri}")

        # Exchange code for access token
        token_response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": google_client_id,
                "client_secret": google_client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=10
        )

        if token_response.status_code != 200:
            print(f">>> Token Exchange Failed: {token_response.text}")
            return Response({"error": "Token exchange failed"}, status=status.HTTP_400_BAD_REQUEST)

        token_data = token_response.json()
        access_token = token_data.get("access_token")

        # Get user info from Google
        user_info_res = requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10
        )

        if user_info_res.status_code != 200:
            return Response({"error": "Failed to get user info"}, status=status.HTTP_400_BAD_REQUEST)

        user_data = user_info_res.json()
        email = user_data.get("email")

        # Find or create user
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "username": email,
                "first_name": user_data.get("given_name", ""),
                "last_name": user_data.get("family_name", ""),
            }
        )

        print(f">>> User {email} logged in (Created: {created})")

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        frontend_redirect = os.getenv("FRONTEND_GOOGLE_REDIRECT_URL")
        if frontend_redirect:
            params = urlencode({
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            })
            return redirect(f"{frontend_redirect}?{params}")

        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": {"email": user.email}
        })
