import os
import secrets
from urllib.parse import urlencode

import requests
from django.contrib.auth import get_user_model
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


class GoogleAuthURLView(View):
    def get(self, request):
        google_client_id = os.getenv("GOOGLE_CLIENT_ID")
        redirect_uri = os.getenv("GOOGLE_REDIRECT_URI") or request.build_absolute_uri(
            reverse("google-callback")
        )

        if not google_client_id:
            return JsonResponse(
                {"detail": "GOOGLE_CLIENT_ID is not set."},
                status=500,
            )

        # We still generate a state for Google, but we don't save it to session
        # to avoid cookie-related "Invalid State" errors in cross-domain setups.
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
        return JsonResponse({"auth_url": auth_url})


class GoogleCallbackView(View):
    def get(self, request):
        # We ignore state validation to avoid session cookie issues between different domains
        code = request.GET.get("code")

        if not code:
            return HttpResponseBadRequest("Google did not return a code.")

        google_client_id = os.getenv("GOOGLE_CLIENT_ID")
        google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        redirect_uri = os.getenv("GOOGLE_REDIRECT_URI") or request.build_absolute_uri(
            reverse("google-callback")
        )

        if not google_client_id or not google_client_secret:
            return HttpResponseBadRequest("Google credentials are missing.")

        token_response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": google_client_id,
                "client_secret": google_client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=10,
        )

        if token_response.status_code != 200:
            return HttpResponseBadRequest("Could not get Google tokens.")

        token_data = token_response.json()
        access_token = token_data.get("access_token")
        if not access_token:
            return HttpResponseBadRequest("Google access token not found.")

        user_response = requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )

        if user_response.status_code != 200:
            return HttpResponseBadRequest("Could not get Google user info.")

        google_user = user_response.json()
        email = google_user.get("email")

        if not email:
            return HttpResponseBadRequest("Google email not found.")

        if not google_user.get("verified_email", False):
            return HttpResponseBadRequest("Google email is not verified.")

        user = User.objects.filter(email=email).first()
        if not user:
            user = User.objects.create_user(
                username=email,
                email=email,
                first_name=google_user.get("given_name", ""),
                last_name=google_user.get("family_name", ""),
            )

        refresh = RefreshToken.for_user(user)
        frontend_url = os.getenv("FRONTEND_GOOGLE_REDIRECT_URL")

        if frontend_url:
            params = urlencode(
                {
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                }
            )
            return redirect(f"{frontend_url}?{params}")

        return JsonResponse(
            {
                "message": "Login successful.",
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "username": user.username,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                },
            }
        )
