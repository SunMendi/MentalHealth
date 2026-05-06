import io
import wave
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from .models import ChatMessage, ChatSession

User = get_user_model()


def _build_wav_file(duration_seconds):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(1)
        wav_file.setframerate(8000)
        wav_file.writeframes(b"\x80" * int(8000 * duration_seconds))

    return SimpleUploadedFile("sample.wav", buffer.getvalue(), content_type="audio/wav")


class ChatSafetyLimitsTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(username="testuser", password="secret123")
        self.client.force_authenticate(user=self.user)
        self.session = ChatSession.objects.create(user=self.user, title="Test Session")

    def tearDown(self):
        cache.clear()

    @patch("core.chat.views.generate_speech_base64", return_value=None)
    @patch("core.chat.views.handle_user_input")
    def test_chat_message_rate_limit_blocks_after_twentieth_request(self, mock_handle_user_input, _mock_tts):
        def fake_handle_user_input(session_id, user_content):
            ChatMessage.objects.create(session_id=session_id, sender="user", content=user_content)
            return ChatMessage.objects.create(session_id=session_id, sender="assistant", content="Support reply")

        mock_handle_user_input.side_effect = fake_handle_user_input
        url = f"/api/chat/sessions/{self.session.id}/messages/"

        for index in range(20):
            response = self.client.post(url, {"content": f"message {index}"}, format="json")
            self.assertEqual(response.status_code, 201)

        blocked_response = self.client.post(url, {"content": "message 21"}, format="json")
        self.assertEqual(blocked_response.status_code, 429)

    @patch("core.chat.views.transcribe_audio", return_value="hello")
    def test_audio_transcription_rate_limit_blocks_after_fifth_request(self, _mock_transcribe):
        url = "/api/voice/transcribe/"

        for _ in range(5):
            response = self.client.post(url, {"audio": _build_wav_file(10)}, format="multipart")
            self.assertEqual(response.status_code, 200)

        blocked_response = self.client.post(url, {"audio": _build_wav_file(10)}, format="multipart")
        self.assertEqual(blocked_response.status_code, 429)

    def test_audio_transcription_rejects_audio_longer_than_three_minutes(self):
        url = "/api/voice/transcribe/"
        response = self.client.post(url, {"audio": _build_wav_file(181)}, format="multipart")

        self.assertEqual(response.status_code, 400)
        self.assertIn("Maximum allowed length is 3 minutes.", response.data["error"])
