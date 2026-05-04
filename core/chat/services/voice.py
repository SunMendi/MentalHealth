import base64
import logging
import os
from typing import Dict, Optional

import edge_tts
import requests

logger = logging.getLogger("chat.voice")

# TTS Settings (Edge TTS)
EDGE_TTS_DEFAULT_VOICE = os.getenv("EDGE_TTS_DEFAULT_VOICE", "en-US-EmmaMultilingualNeural")
EDGE_TTS_BN_VOICE = os.getenv("EDGE_TTS_BN_VOICE", "bn-BD-NabanitaNeural")

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


async def generate_speech_base64(text: str, voice: Optional[str] = None) -> Optional[Dict[str, str]]:
    """
    Generates high-quality speech using Edge TTS and returns a Base64 string.
    """
    selected_voice = voice or choose_tts_voice(text)
    logger.info("Starting TTS generation | voice=%s | length=%d", selected_voice, len(text or ""))

    try:
        communicate = edge_tts.Communicate(text, selected_voice)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]

        if not audio_data:
            logger.warning("Edge TTS returned empty audio buffer")
            return None

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
