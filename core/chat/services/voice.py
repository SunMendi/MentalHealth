import os
import logging
import base64
import edge_tts
from typing import Dict, Optional
from elevenlabs.client import ElevenLabs

logger = logging.getLogger("chat.voice")

# Use scribe_v1 as default for broader compatibility
ELEVENLABS_STT_MODEL = os.getenv("ELEVENLABS_STT_MODEL", "scribe_v1")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "").strip().strip("\"'")

if not ELEVENLABS_API_KEY:
    logger.error("Environment Variable ELEVENLABS_API_KEY is missing. transcription will fail.")

# Initialize official ElevenLabs client
client = ElevenLabs(api_key=ELEVENLABS_API_KEY) if ELEVENLABS_API_KEY else None


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
        return os.getenv("EDGE_TTS_BN_VOICE", "bn-BD-NabanitaNeural")
    return os.getenv("EDGE_TTS_DEFAULT_VOICE", "en-US-EmmaMultilingualNeural")


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
            "voice": selected_voice
        }
    except Exception as e:
        logger.exception("In-memory TTS generation failed: %s", e)
        return None


def transcribe_audio(audio_file_path: str) -> Optional[str]:
    """
    Transcribes audio to text using the official ElevenLabs Python SDK.
    """
    if not client:
        logger.error("STT skipped because ElevenLabs client is not initialized")
        return None

    try:
        if not os.path.exists(audio_file_path):
            logger.error("Transcription failed: Audio file not found at %s", audio_file_path)
            return None

        logger.info(
            "Starting ElevenLabs SDK STT | model=%s | file=%s | key_hint=%s",
            ELEVENLABS_STT_MODEL,
            os.path.basename(audio_file_path),
            _mask_key(ELEVENLABS_API_KEY),
        )

        with open(audio_file_path, "rb") as f:
            transcription = client.speech_to_text.convert(
                file=f,
                model_id="scribe_v2",
                tag_audio_events=True,
                diarize=True,
                language_code=None, # Auto-detect for Bengali/English support
            )
            
            text = (transcription.text or "").strip()
            logger.info("ElevenLabs SDK transcription success | text_preview=%s", text[:50])
            return text

    except Exception as e:
        logger.exception(
            "ElevenLabs SDK transcription failed | file=%s | error=%s",
            os.path.basename(audio_file_path),
            e
        )
        return None
