import os
import logging
import base64
import edge_tts
import requests
from typing import Dict, Optional

logger = logging.getLogger("chat.voice")

ELEVENLABS_STT_MODEL = os.getenv("ELEVENLABS_STT_MODEL", "scribe_v2")
ELEVENLABS_STT_URL = "https://api.elevenlabs.io/v1/speech-to-text"
ELEVENLABS_STT_TIMEOUT_SECONDS = int(os.getenv("ELEVENLABS_STT_TIMEOUT_SECONDS", "60"))

if not os.getenv("ELEVENLABS_API_KEY"):
    logger.error("Environment Variable ELEVENLABS_API_KEY is missing. transcription will fail.")


def _get_elevenlabs_api_key() -> str:
    """
    Read the key at call time so deploy-time env changes work after restart,
    and normalize common copy/paste issues like surrounding quotes/spaces.
    """
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
    # Simple range-based Bengali detection (U+0980 to U+09FF)
    if any("\u0980" <= ch <= "\u09FF" for ch in (text or "")):
        return os.getenv("EDGE_TTS_BN_VOICE", "bn-BD-NabanitaNeural")
    return os.getenv("EDGE_TTS_DEFAULT_VOICE", "en-US-EmmaMultilingualNeural")


async def generate_speech_base64(text: str, voice: Optional[str] = None) -> Optional[Dict[str, str]]:
    """
    Generates high-quality speech using Edge TTS and returns a Base64 string.
    
    Architecture Design:
    - Zero Disk I/O: Audio is streamed in-memory and converted to Base64.
    - Privacy: No sensitive audio files are saved to the server.
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
            "voice": selected_voice
        }
    except Exception as e:
        logger.exception("In-memory TTS generation failed: %s", e)
        return None


def transcribe_audio(audio_file_path: str) -> Optional[str]:
    """
    Transcribes audio to text using ElevenLabs Speech-to-Text.
    
    Reliability Features:
    - Scribe v2: Accurate multilingual transcription for Bengali/English voice input.
    - Auto Language Detection: Lets mixed Bangla/English speech route through one path.
    - Managed Cleanup: Temp files are expected to be handled by the calling view.
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
            "Starting ElevenLabs STT transcription | model=%s | audio_file_path=%s | key_hint=%s",
            ELEVENLABS_STT_MODEL,
            audio_file_path,
            _mask_key(api_key),
        )
        with open(audio_file_path, "rb") as file:
            data = {
                "model_id": ELEVENLABS_STT_MODEL,
                "tag_audio_events": "false",
                "diarize": "false",
                "timestamps_granularity": "none",
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
                        file,
                        "application/octet-stream",
                    )
                },
                timeout=ELEVENLABS_STT_TIMEOUT_SECONDS,
            )
            response.raise_for_status()

            payload = response.json()
            text = (payload.get("text") or "").strip()
            logger.info(
                "ElevenLabs transcription successful | char_count=%d | text_preview=%s",
                len(text),
                text[:80],
            )
            return text

    except requests.RequestException as e:
        response_text = getattr(e.response, "text", "") if getattr(e, "response", None) else ""
        status_code = getattr(e.response, "status_code", None) if getattr(e, "response", None) else None
        logger.exception(
            "ElevenLabs STT API call failed | audio_file_path=%s | status_code=%s | key_hint=%s | error=%s | response=%s",
            audio_file_path,
            status_code,
            _mask_key(api_key),
            e,
            response_text[:500],
        )
        return None
    except Exception as e:
        logger.exception("ElevenLabs transcription failed | audio_file_path=%s | error=%s", audio_file_path, e)
        return None
