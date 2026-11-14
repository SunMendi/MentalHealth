import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APITestCase

from .models import ChatSession


class MessageStreamHeaderTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="stream-header-test")
        cls.session = ChatSession.objects.create(user=cls.user, title="Stream test")

    def setUp(self):
        cache.clear()
        self.client.force_authenticate(self.user)
        self.url = reverse("message-stream", args=[self.session.id])

    def tearDown(self):
        cache.clear()

    def post(self, content="Hello", accept="text/event-stream", url=None):
        return self.client.post(
            url or self.url, {"content": content}, format="json", HTTP_ACCEPT=accept
        )

    @patch("chat.views.handle_user_input_stream")
    def test_mobile_accept_header_returns_tokens_and_final_audio(self, brain):
        events = [
            {"type": "user_message", "message": {"id": 1}},
            {"type": "token", "content": "Hello"},
            {"type": "done", "assistant_message": {"id": 2, "content": "Hello"}, "audio_base64": "ZmFrZQ=="},
        ]
        brain.return_value = iter(events)
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/event-stream")
        self.assertEqual(response["Cache-Control"], "no-cache")
        self.assertEqual(response["X-Accel-Buffering"], "no")
        payload = b"".join(response.streaming_content).decode()
        received = [json.loads(frame.removeprefix("data: ")) for frame in payload.strip().split("\n\n")]
        self.assertEqual(received, events)
        brain.assert_called_once_with(self.session.id, "Hello")

    @patch("chat.views.handle_user_input_stream", return_value=iter([]))
    def test_json_and_wildcard_headers_still_stream(self, brain):
        for accept in ("application/json", "*/*", "text/event-stream, application/json"):
            with self.subTest(accept=accept):
                response = self.post(accept=accept)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Content-Type"], "text/event-stream")
                response.close()

    @patch("chat.views.handle_user_input_stream")
    def test_blank_message_returns_json_validation_error(self, brain):
        response = self.post(content="   ")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(response.json(), {"error": "No content provided"})
        brain.assert_not_called()

    def test_missing_authentication_returns_json_401(self):
        self.client.force_authenticate(user=None)
        response = self.post()
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertIn("detail", response.json())

    def test_expired_authentication_returns_json_401(self):
        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid-token")
        response = self.post()
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response["Content-Type"], "application/json")

    @patch("chat.views.handle_user_input_stream")
    def test_other_users_session_is_not_accessible(self, brain):
        other = get_user_model().objects.create_user(username="other-stream-user")
        self.client.force_authenticate(other)
        response = self.post()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response["Content-Type"], "application/json")
        brain.assert_not_called()

    @patch("chat.views.handle_user_input_stream")
    def test_unknown_session_returns_json_404(self, brain):
        response = self.post(url=reverse("message-stream", args=[self.session.id + 1000]))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response["Content-Type"], "application/json")
        brain.assert_not_called()

    @patch("chat.throttles.ChatMessageRateThrottle.rate", "1/hour")
    @patch("chat.views.handle_user_input_stream", return_value=iter([]))
    def test_throttle_still_returns_json_429(self, brain):
        first = self.post()
        self.assertEqual(first.status_code, 200)
        first.close()
        blocked = self.post()
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(blocked["Content-Type"], "application/json")
        self.assertIn("Retry-After", blocked)

    def test_unsupported_accept_header_remains_406(self):
        response = self.post(accept="application/xml")
        self.assertEqual(response.status_code, 406)

    @patch("chat.views.handle_user_input_stream", side_effect=RuntimeError("provider unavailable"))
    def test_generation_error_remains_a_stream_error(self, brain):
        response = self.post()
        self.assertEqual(response.status_code, 200)
        event = json.loads(b"".join(response.streaming_content).decode().strip().removeprefix("data: "))
        self.assertEqual(event, {"type": "error", "message": "Failed to generate response."})
