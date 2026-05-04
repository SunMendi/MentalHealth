import os
import logging
import base64
import edge_tts
from typing import Dict, Optional
from groq import Groq

logger = logging.getLogger("chat.voice")

# TTS Settings (Edge TTS)
EDGE_TTS_DEFAULT_VOICE = os.getenv("EDGE_TTS_DEFAULT_VOICE", "en-US-EmmaMultilingualNeural")
EDGE_TTS_BN_VOICE = os.getenv("EDGE_TTS_BN_VOICE", "bn-BD-NabanitaNeural")

# STT Settings (Groq Whisper)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_STT_MODEL = os.getenv("GROQ_STT_MODEL", "whisper-large-v3")

if not GROQ_API_KEY:
    logger.error("Environment Variable GROQ_API_KEY is missing. Transcription will fail.")

# Groq Client Initialization
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None


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
            "voice": selected_voice
        }
    except Exception as e:
        logger.exception("In-memory TTS generation failed: %s", e)
        return None


def transcribe_audio(audio_file_path: str) -> Optional[str]:
    """
    Transcribes audio to text using Groq Whisper.
    
    Reliability Features:
    - Whisper Large V3: High accuracy for mixed English/Bengali speech.
    - Cloud Optimized: Bypasses IP blocks that affect ElevenLabs Free Tier.
    """
    if not groq_client:
        logger.error("STT skipped because GROQ_API_KEY is missing")
        return None

    try:
        if not os.path.exists(audio_file_path):
            logger.error("Transcription failed: Audio file not found at %s", audio_file_path)
            return None

        logger.info(
            "Starting Groq STT transcription | model=%s | file=%s",
            GROQ_STT_MODEL,
            os.path.basename(audio_file_path),
        )

        with open(audio_file_path, "rb") as file:
            transcription = groq_client.audio.transcriptions.create(
                file=(os.path.basename(audio_file_path), file.read()),
                model=GROQ_STT_MODEL,
                response_format="json",
            )
            
            text = (transcription.text or "").strip()
            logger.info("Groq transcription success | text_preview=%s", text[:50])
            return text

    except Exception as e:
        logger.exception("Groq transcription failed | file=%s | error=%s", os.path.basename(audio_file_path), e)
        return None
