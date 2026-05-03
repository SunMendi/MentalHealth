import os
import logging
import base64
import edge_tts
from groq import Groq
from typing import Dict, Any, Optional

logger = logging.getLogger("chat.voice")

# Initialize Groq client for Speech-to-Text
# Engineers: We use Groq's high-speed LPU infrastructure for near-instant transcription.
# Model: whisper-large-v3-turbo (State-of-the-art for bilingual Bengali/English)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    logger.error("Environment Variable GROQ_API_KEY is missing. transcription will fail.")

client = Groq(api_key=GROQ_API_KEY)


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
    Transcribes audio to text using Groq's whisper-large-v3-turbo.
    
    Reliability Features:
    - Turbo Speed: Optimized for low-latency conversational AI.
    - Context Prompt: Injects mental health terminology to reduce transcription errors.
    - Managed Cleanup: Temp files are expected to be handled by the calling view.
    """
    if not GROQ_API_KEY:
        return None

    try:
        if not os.path.exists(audio_file_path):
            logger.error("Transcription failed: Audio file not found at %s", audio_file_path)
            return None

        with open(audio_file_path, "rb") as file:
            # Engineers: Using 'whisper-large-v3-turbo' for the best balance of speed and accuracy.
            transcription = client.audio.transcriptions.create(
                file=(os.path.basename(audio_file_path), file.read()),
                model="whisper-large-v3-turbo",
                response_format="json",
                # This prompt acts as a linguistic guide for the model
                prompt="The user is discussing mental health, feelings, and emotional support in English or Bengali (Bangla).",
                temperature=0.0
            )
            
            text = transcription.text.strip() if transcription and transcription.text else ""
            logger.info("Groq Turbo transcription successful | char_count=%d", len(text))
            return text

    except Exception as e:
        logger.error("Groq Whisper Turbo API call failed: %s", str(e))
        return None
