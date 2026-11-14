import asyncio
import base64
import logging
import os
import re
from time import monotonic
from typing import Dict, Optional

import edge_tts
import requests

logger = logging.getLogger("chat.voice")

# TTS Settings (Edge TTS)
EDGE_TTS_DEFAULT_VOICE = os.getenv("EDGE_TTS_DEFAULT_VOICE", "en-US-EmmaMultilingualNeural")
EDGE_TTS_BN_VOICE = os.getenv("EDGE_TTS_BN_VOICE", "bn-BD-NabanitaNeural")
EDGE_TTS_MAX_CHUNKS = max(1, min(3, int(os.getenv("EDGE_TTS_MAX_CHUNKS", "3"))))
EDGE_TTS_TIMEOUT_SECONDS = float(os.getenv("EDGE_TTS_TIMEOUT_SECONDS", "30"))

# STT Settings (ElevenLabs)
ELEVENLABS_STT_URL = "https://api.elevenlabs.io/v1/speech-to-text"
ELEVENLABS_STT_MODEL = os.getenv("ELEVENLABS_STT_MODEL", "scribe_v2")
ELEVENLABS_STT_TIMEOUT_SECONDS = int(os.getenv("ELEVENLABS_STT_TIMEOUT_SECONDS", "60"))

if not os.getenv("ELEVENLABS_API_KEY"):
    logger.error("Environment Variable ELEVENLABS_API_KEY is missing. Transcription will fail.")


def _get_elevenlabs_api_key() -> str:
    raw_key = os.getenv("ELEVENLABS_API_KEY", "")
    return raw_key.strip().strip("\"'")


def _mask_key(key: str) -> str:
    if not key:
        return "missing"
    if len(key) <= 8:
        return f"{key[:2]}...{key[-2:]}"
    return f"{key[:4]}...{key[-4:]}"


def choose_tts_voice(text: str) -> str:
    """
    Selects the best neural voice based on language detection (Bengali vs English).
    """
    if any("\u0980" <= ch <= "\u09FF" for ch in (text or "")):
        return EDGE_TTS_BN_VOICE
    return EDGE_TTS_DEFAULT_VOICE


def _split_speech_text(text: str) -> list[str]:
    """Balance complete sentences across at most three synthesis requests.

    Keep every character in its original order. Short replies and single
    sentences use one request, avoiding extra connection overhead.
    """
    if len(text) < 180 or EDGE_TTS_MAX_CHUNKS == 1:
        return [text]

    sentences = re.split(r"(?<=[.!?।])(?=\s+\S)", text)
    count = min(EDGE_TTS_MAX_CHUNKS, len(sentences))
    chunks = []
    while count > 1:
        target = sum(map(len, sentences)) / count
        length = 0
        candidates = []
        for end in range(1, len(sentences) - count + 2):
            length += len(sentences[end - 1])
            candidates.append((abs(length - target), end))
        _, end = min(candidates)
        chunks.append("".join(sentences[:end]))
        sentences = sentences[end:]
        count -= 1
    chunks.append("".join(sentences))
    return chunks


async def _synthesize_speech_chunk(text: str, voice: str) -> bytes:
    audio = bytearray()
    async for chunk in edge_tts.Communicate(text, voice).stream():
        if chunk["type"] == "audio":
            audio.extend(chunk["data"])
    if not audio:
        raise ValueError("Edge TTS returned no audio")
    return bytes(audio)


async def _synthesize_speech_chunks(chunks: list[str], voice: str) -> bytes:
    tasks = [asyncio.create_task(_synthesize_speech_chunk(chunk, voice)) for chunk in chunks]
    try:
        # Edge TTS returns headerless, fixed-format MP3 frames. Joining complete
        # results in text order keeps one MP3 compatible with existing players.
        return b"".join(await asyncio.gather(*tasks))
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def generate_speech_base64(text: str, voice: Optional[str] = None) -> Optional[Dict[str, str]]:
    """Generate one complete MP3, synthesizing sentence groups concurrently."""
    if not text or not text.strip():
        return None
    selected_voice = voice or choose_tts_voice(text)
    # Production benchmarks showed no consistent gain from parallel Bengali
    # requests. Keep those voices on one request rather than adding overhead.
    chunks = [text] if selected_voice.startswith("bn-") else _split_speech_text(text)
    started = monotonic()
    logger.info("Starting TTS generation | voice=%s | length=%d | chunks=%d", selected_voice, len(text), len(chunks))

    try:
        async with asyncio.timeout(EDGE_TTS_TIMEOUT_SECONDS):
            if len(chunks) == 1:
                audio_data = await _synthesize_speech_chunk(text, selected_voice)
            else:
                try:
                    audio_data = await _synthesize_speech_chunks(chunks, selected_voice)
                except Exception:
                    # Never return a reply missing a sentence. Retry the full
                    # text once within the same overall deadline.
                    logger.warning("Parallel TTS failed; retrying full text | voice=%s", selected_voice)
                    audio_data = await _synthesize_speech_chunk(text, selected_voice)

        logger.info(
            "TTS generation complete | voice=%s | chunks=%d | duration_s=%.3f | audio_bytes=%d",
            selected_voice, len(chunks), monotonic() - started, len(audio_data),
        )

        return {
            "base64": base64.b64encode(audio_data).decode("utf-8"),
            "voice": selected_voice,
        }
    except Exception as exc:
        logger.exception("In-memory TTS generation failed: %s", exc)
        return None


def transcribe_audio(audio_file_path: str) -> Optional[str]:
    """
    Transcribes audio to text using ElevenLabs Speech-to-Text.
    """
    api_key = _get_elevenlabs_api_key()
    if not api_key:
        logger.error("STT skipped because ELEVENLABS_API_KEY is missing")
        return None

    try:
        if not os.path.exists(audio_file_path):
            logger.error("Transcription failed: Audio file not found at %s", audio_file_path)
            return None

        logger.info(
            "Starting ElevenLabs STT transcription | model=%s | file=%s | key_hint=%s",
            ELEVENLABS_STT_MODEL,
            os.path.basename(audio_file_path),
            _mask_key(api_key),
        )

        with open(audio_file_path, "rb") as audio_file:
            data = {
                "model_id": ELEVENLABS_STT_MODEL,
                "diarize": "false",
                "tag_audio_events": "false",
            }
            language_code = os.getenv("ELEVENLABS_STT_LANGUAGE_CODE")
            if language_code:
                data["language_code"] = language_code

            response = requests.post(
                ELEVENLABS_STT_URL,
                headers={"xi-api-key": api_key},
                data=data,
                files={
                    "file": (
                        os.path.basename(audio_file_path),
                        audio_file,
                        "application/octet-stream",
                    )
                },
                timeout=ELEVENLABS_STT_TIMEOUT_SECONDS,
            )
            response.raise_for_status()

        payload = response.json()
        text = (payload.get("text") or "").strip()
        logger.info("ElevenLabs transcription success | text_preview=%s", text[:80])
        return text

    except requests.RequestException as exc:
        response_text = getattr(exc.response, "text", "") if getattr(exc, "response", None) else ""
        status_code = getattr(exc.response, "status_code", None) if getattr(exc, "response", None) else None
        logger.exception(
            "ElevenLabs STT API call failed | file=%s | status_code=%s | key_hint=%s | error=%s | response=%s",
            os.path.basename(audio_file_path),
            status_code,
            _mask_key(api_key),
            exc,
            response_text[:500],
        )
        return None
    except Exception as exc:
        logger.exception(
            "ElevenLabs transcription failed | file=%s | error=%s",
            os.path.basename(audio_file_path),
            exc,
        )
        return None
