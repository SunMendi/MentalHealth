import asyncio
import base64
from unittest.mock import patch

from django.test import SimpleTestCase

from .services import voice


LONG_TEXT = (
    "You have had a full day and can take a quiet moment now. "
    "There is no need to solve every problem this evening. "
    "Notice the support under your feet and let your shoulders rest. "
    "You could choose a glass of water or a few minutes away from your screen. "
    "What small thing would make this moment easier for you?"
)


class SpeechChunkingTests(SimpleTestCase):
    def test_short_replies_and_single_sentences_use_one_request(self):
        for text in ("Hello. How are you?", "a " * 150, LONG_TEXT):
            with self.subTest(text_length=len(text)):
                if text == LONG_TEXT:
                    with patch.object(voice, "EDGE_TTS_MAX_CHUNKS", 1):
                        self.assertEqual(voice._split_speech_text(text), [text])
                else:
                    self.assertEqual(voice._split_speech_text(text), [text])

    def test_chunks_preserve_every_character_in_english_bangla_and_mixed_text(self):
        texts = [
            LONG_TEXT,
            "আজকের দিনটি আপনার জন্য অনেক ব্যস্ত ছিল। এখন সব সমস্যার সমাধান করতে হবে না। " * 5,
            "  " + LONG_TEXT.replace(". ", ".\n\n") + "  \n",
            "The number is 3.5. " + LONG_TEXT + " নিজের জন্য সময় নিন।",
        ]
        for text in texts:
            with self.subTest(text=text[:30]):
                chunks = voice._split_speech_text(text)
                self.assertGreater(len(chunks), 1)
                self.assertLessEqual(len(chunks), 3)
                self.assertEqual("".join(chunks), text)
                self.assertTrue(all(chunk.strip() for chunk in chunks))

    def test_very_long_input_still_has_at_most_three_parallel_requests(self):
        chunks = voice._split_speech_text(LONG_TEXT * 100)
        self.assertEqual(len(chunks), 3)
        self.assertEqual("".join(chunks), LONG_TEXT * 100)

    async def test_sentence_groups_run_concurrently_and_join_in_text_order(self):
        parts = voice._split_speech_text(LONG_TEXT)
        entered = []
        gates = {part: asyncio.Event() for part in parts}
        all_started = asyncio.Event()

        async def synthesize(text, selected_voice):
            entered.append(text)
            if len(entered) == len(parts):
                all_started.set()
            await gates[text].wait()
            return str(parts.index(text)).encode()

        with patch.object(voice, "_synthesize_speech_chunk", side_effect=synthesize):
            task = asyncio.create_task(voice.generate_speech_base64(LONG_TEXT))
            try:
                await asyncio.wait_for(all_started.wait(), 1)
                for part in reversed(parts):
                    gates[part].set()
                result = await task
            finally:
                for gate in gates.values():
                    gate.set()
                await task
        self.assertEqual(base64.b64decode(result["base64"]), b"012")
        self.assertEqual(result["voice"], voice.EDGE_TTS_DEFAULT_VOICE)

    async def test_mixed_language_reply_keeps_one_voice_for_every_chunk(self):
        text = LONG_TEXT + " নিজের জন্য সময় নিন।"
        with patch.object(voice, "_synthesize_speech_chunk", return_value=b"audio") as synthesize:
            result = await voice.generate_speech_base64(text)
        self.assertEqual(result["voice"], voice.EDGE_TTS_BN_VOICE)
        self.assertTrue(all(call.args[1] == voice.EDGE_TTS_BN_VOICE for call in synthesize.call_args_list))

    async def test_explicit_voice_is_preserved(self):
        with patch.object(voice, "_synthesize_speech_chunk", return_value=b"audio") as synthesize:
            result = await voice.generate_speech_base64(LONG_TEXT, voice="custom-voice")
        self.assertEqual(result["voice"], "custom-voice")
        self.assertTrue(all(call.args[1] == "custom-voice" for call in synthesize.call_args_list))

    async def test_bengali_voice_uses_one_complete_request(self):
        text = "আজকের দিনটি আপনার জন্য অনেক ব্যস্ত ছিল। এখন সব সমস্যার সমাধান করতে হবে না। " * 5
        with patch.object(voice, "_synthesize_speech_chunk", return_value=b"audio") as synthesize:
            result = await voice.generate_speech_base64(text)
        self.assertEqual(result["voice"], voice.EDGE_TTS_BN_VOICE)
        synthesize.assert_awaited_once_with(text, voice.EDGE_TTS_BN_VOICE)

    async def test_failed_chunk_retries_complete_text_without_returning_partial_audio(self):
        parts = voice._split_speech_text(LONG_TEXT)

        async def synthesize(text, selected_voice):
            if text == LONG_TEXT:
                return b"complete fallback audio"
            if text == parts[1]:
                raise RuntimeError("Provider rejected one chunk")
            return b"partial audio"

        with patch.object(voice, "_synthesize_speech_chunk", side_effect=synthesize) as synthesize_mock:
            result = await voice.generate_speech_base64(LONG_TEXT)
        self.assertEqual(base64.b64decode(result["base64"]), b"complete fallback audio")
        self.assertEqual(synthesize_mock.call_count, len(parts) + 1)

    async def test_failed_parallel_and_fallback_requests_return_no_incomplete_audio(self):
        with patch.object(voice, "_synthesize_speech_chunk", side_effect=RuntimeError("Provider unavailable")):
            self.assertIsNone(await voice.generate_speech_base64(LONG_TEXT))

    async def test_timeout_cancels_all_active_chunks(self):
        active = set()

        async def synthesize(text, selected_voice):
            active.add(text)
            try:
                await asyncio.Event().wait()
            finally:
                active.remove(text)

        with (
            patch.object(voice, "EDGE_TTS_TIMEOUT_SECONDS", 0.02),
            patch.object(voice, "_synthesize_speech_chunk", side_effect=synthesize),
        ):
            self.assertIsNone(await voice.generate_speech_base64(LONG_TEXT))
        self.assertEqual(active, set())

    async def test_caller_cancellation_stops_every_chunk_without_retry(self):
        active = set()
        ready = asyncio.Event()
        parts = voice._split_speech_text(LONG_TEXT)

        async def synthesize(text, selected_voice):
            active.add(text)
            if len(active) == len(parts):
                ready.set()
            try:
                await asyncio.Event().wait()
            finally:
                active.remove(text)

        with patch.object(voice, "_synthesize_speech_chunk", side_effect=synthesize) as synthesize_mock:
            task = asyncio.create_task(voice.generate_speech_base64(LONG_TEXT))
            await asyncio.wait_for(ready.wait(), 1)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertEqual(active, set())
        self.assertEqual(synthesize_mock.call_count, len(parts))

    async def test_synthesis_ignores_metadata_but_requires_audio(self):
        class Communicate:
            def __init__(self, text, selected_voice):
                self.text = text

            async def stream(self):
                yield {"type": "SentenceBoundary", "text": self.text}
                if self.text == "has audio":
                    yield {"type": "audio", "data": b"first"}
                    yield {"type": "audio", "data": b"second"}

        with patch.object(voice.edge_tts, "Communicate", Communicate):
            result = await voice.generate_speech_base64("has audio")
            self.assertEqual(base64.b64decode(result["base64"]), b"firstsecond")
            self.assertIsNone(await voice.generate_speech_base64("empty audio"))

    async def test_blank_input_does_not_contact_speech_provider(self):
        with patch.object(voice.edge_tts, "Communicate") as communicate:
            for text in ("", " \n "):
                self.assertIsNone(await voice.generate_speech_base64(text))
            communicate.assert_not_called()
