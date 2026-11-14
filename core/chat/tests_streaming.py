import asyncio
import base64
import json
import threading
from types import SimpleNamespace
from unittest.mock import patch

from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import AsyncClient, AsyncRequestFactory, SimpleTestCase, TransactionTestCase
from rest_framework.test import force_authenticate
from rest_framework_simplejwt.tokens import AccessToken

from .models import ChatMessage, ChatSession
from .streaming import async_stream
from .views import MessageStreamAPIView


class AsyncChatStreamingTests(SimpleTestCase):
    async def test_each_event_arrives_before_later_work_starts(self):
        produced = []
        closed = []

        def events():
            try:
                for item in ("first text", "later text", "final audio"):
                    produced.append(item)
                    yield item
            finally:
                closed.append(True)

        stream = async_stream(events())
        self.assertEqual(await anext(stream), "first text")
        self.assertEqual(produced, ["first text"])
        self.assertEqual(await anext(stream), "later text")
        self.assertEqual(produced, ["first text", "later text"])
        await stream.aclose()
        self.assertEqual(closed, [True])
        self.assertNotIn("final audio", produced)

    async def test_provider_wait_does_not_block_other_async_requests(self):
        entered = threading.Event()
        release = threading.Event()
        threads = []
        main_thread = threading.get_ident()

        def slow_events():
            threads.append(threading.get_ident())
            entered.set()
            if not release.wait(timeout=5):
                raise TimeoutError("Test did not release the provider")
            yield "slow reply"
            threads.append(threading.get_ident())
            yield "next token"

        slow = async_stream(slow_events())
        pending = asyncio.create_task(anext(slow))
        try:
            self.assertTrue(await asyncio.to_thread(entered.wait, 2))
            fast = async_stream(iter(["another user's reply"]))
            self.assertEqual(await asyncio.wait_for(anext(fast), 1), "another user's reply")
            await fast.aclose()
            self.assertFalse(pending.done())
            release.set()
            self.assertEqual(await pending, "slow reply")
            self.assertEqual(await anext(slow), "next token")
            self.assertEqual(len(set(threads)), 1)
            self.assertNotEqual(threads[0], main_thread)
        finally:
            release.set()
            await pending
            await slow.aclose()

    async def test_generator_error_closes_its_resources(self):
        closed = []

        def events():
            try:
                yield "first"
                raise RuntimeError("Provider failure")
            finally:
                closed.append(True)

        stream = async_stream(events())
        self.assertEqual(await anext(stream), "first")
        with self.assertRaisesMessage(RuntimeError, "Provider failure"):
            await anext(stream)
        self.assertEqual(closed, [True])

    async def test_client_disconnect_cancels_generation_and_cleans_up(self):
        entered = threading.Event()
        release = threading.Event()
        closed = []
        produced = []

        def events():
            try:
                yield "first"
                entered.set()
                if not release.wait(timeout=5):
                    raise TimeoutError("Test did not release the provider")
                yield "in progress"
                produced.append("unneeded work")
                yield "final audio"
            finally:
                closed.append(True)

        stream = async_stream(events())
        self.assertEqual(await anext(stream), "first")
        pending = asyncio.create_task(anext(stream))
        self.assertTrue(await asyncio.to_thread(entered.wait, 2))
        pending.cancel()
        release.set()
        with self.assertRaises(asyncio.CancelledError):
            await pending
        self.assertEqual(closed, [True])
        self.assertEqual(produced, [])

    async def test_asgi_endpoint_returns_a_real_async_stream(self):
        request = AsyncRequestFactory().post(
            "/api/chat/sessions/1/messages/stream/",
            json.dumps({"content": "Hello"}),
            content_type="application/json",
            headers={"Accept": "text/event-stream"},
        )
        force_authenticate(request, user=SimpleNamespace(id=1, is_authenticated=True))
        produced = []

        def events(*args):
            produced.append("first")
            yield {"type": "token", "content": "Hello"}
            produced.append("audio")
            yield {"type": "done", "audio_base64": "ZmFrZQ=="}

        with (
            patch("chat.views.get_object_or_404", return_value=SimpleNamespace(id=1)),
            patch.object(MessageStreamAPIView, "get_throttles", return_value=[]),
            patch("chat.views.handle_user_input_stream", side_effect=events),
        ):
            response = await sync_to_async(MessageStreamAPIView.as_view())(request, session_id=1)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.is_async)
            stream = response.streaming_content
            first = await anext(stream)
            self.assertIn(b'"content": "Hello"', first)
            self.assertEqual(produced, ["first"])
            remaining = [chunk async for chunk in stream]
            self.assertEqual(len(remaining), 1)
            self.assertIn(b'"audio_base64": "ZmFrZQ=="', remaining[0])
            self.assertEqual(produced, ["first", "audio"])
            await sync_to_async(response.close)()


class ASGIChatDatabaseTests(TransactionTestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(username="asgi-stream-user")
        self.session = ChatSession.objects.create(user=self.user, title="ASGI database test")
        self.token = str(AccessToken.for_user(self.user))

    def tearDown(self):
        cache.clear()

    async def post_stream(self, content):
        return await AsyncClient().post(
            f"/api/chat/sessions/{self.session.id}/messages/stream/",
            {"content": content},
            content_type="application/json",
            headers={"Accept": "text/event-stream", "Authorization": f"Bearer {self.token}"},
        )

    async def test_real_orchestrator_saves_messages_and_finishes_with_tts(self):
        with (
            patch("chat.services.brain.check_for_crisis", return_value=False),
            patch("chat.services.brain.triage_user_message", return_value={"mode": "supportive"}),
            patch("chat.services.brain.run_agent_loop_stream", return_value=iter([
                {"type": "token", "content": "Hello. How are you feeling?"},
                {"type": "agent_finished", "buttons": ["Tell you more"], "iterations": 1},
            ])),
            patch("chat.services.brain.generate_speech_base64", return_value={"base64": "ZmFrZQ==", "voice": "test-voice"}),
        ):
            response = await self.post_stream("Hello")
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.is_async)
            frames = [chunk async for chunk in response.streaming_content]

        events = [json.loads(frame.decode().strip().removeprefix("data: ")) for frame in frames]
        self.assertEqual(events[0]["type"], "user_message")
        self.assertTrue(any(event["type"] == "token" for event in events))
        self.assertEqual(events[-1]["type"], "done")
        self.assertEqual(base64.b64decode(events[-1]["audio_base64"]), b"fake")
        self.assertEqual(events[-1]["assistant_message"]["metadata"]["tts_voice"], "test-voice")
        saved = await sync_to_async(list)(ChatMessage.objects.filter(session=self.session).order_by("created_at").values_list("sender", flat=True))
        self.assertEqual(saved, ["user", "assistant"])

    async def test_crisis_still_bypasses_triage_normal_chat_and_tts(self):
        crisis = SimpleNamespace(content="Please reach someone you trust now.", suggested_replies=["Contact someone"], executed_tools=[])
        with (
            patch("chat.services.brain.handle_crisis_flow", return_value=crisis),
            patch("chat.services.brain.triage_user_message") as triage,
            patch("chat.services.brain.run_agent_loop_stream") as normal_chat,
            patch("chat.services.brain.generate_speech_base64") as tts,
        ):
            response = await self.post_stream("I want to die")
            self.assertEqual(response.status_code, 200)
            frames = [chunk async for chunk in response.streaming_content]
            triage.assert_not_called()
            normal_chat.assert_not_called()
            tts.assert_not_called()
        done = json.loads(frames[-1].decode().strip().removeprefix("data: "))
        self.assertTrue(done["assistant_message"]["metadata"]["is_crisis"])
        self.assertIsNone(done["audio_base64"])
