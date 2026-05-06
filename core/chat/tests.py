import io
import wave
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from .models import ChatMessage, ChatSession
from .services.support_planner import build_support_plan, detect_current_need

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

    @patch("core.chat.views.generate_speech_base64", return_value={"base64": "ZmFrZQ==", "voice": "en-US-EmmaMultilingualNeural"})
    def test_standalone_tts_returns_audio_base64(self, _mock_tts):
        response = self.client.post("/api/voice/tts/", {"text": "You're safe. Breathe in and out."}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["audio_base64"], "ZmFrZQ==")
        self.assertEqual(response.data["voice"], "en-US-EmmaMultilingualNeural")

    def test_standalone_tts_rejects_blank_text(self):
        response = self.client.post("/api/voice/tts/", {"text": ""}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("text", response.data)


class SupportPlannerTests(TestCase):
    def test_detect_current_need_story_request(self):
        need = detect_current_need("Please tell me a short story that helps me calm down")
        self.assertEqual(need, "STORY")

    def test_detect_current_need_medical_check_for_chest_pain(self):
        need = detect_current_need("I feel pain in my chest and I cannot breathe properly")
        self.assertEqual(need, "MEDICAL_CHECK")

    def test_support_plan_prefers_problem_solving_for_work_stress(self):
        plan = build_support_plan(
            user_content="I have too many tasks and I need to decide what to do first",
            category_name="Workplace Stress",
            protocol_text="Problem solving protocol",
            recent_interventions=[],
        )
        self.assertEqual(plan["current_need"], "ADVICE")
        self.assertEqual(plan["response_style"], "warm_reflective")
        self.assertIn("one practical next step", plan["next_step"].lower())

    def test_support_plan_uses_reframing_for_overthinking(self):
        plan = build_support_plan(
            user_content="I keep overthinking and my thoughts won't stop",
            category_name="General Anxiety",
            protocol_text="CBT protocol",
            recent_interventions=[],
        )
        self.assertEqual(plan["current_need"], "REFRAMING")
        self.assertEqual(plan["response_style"], "gentle_cbt")
