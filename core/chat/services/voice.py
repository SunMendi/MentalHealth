import os
import logging
import base64
import edge_tts
from groq import Groq

logger = logging.getLogger("chat.voice")

# Initialize Groq client
client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def choose_tts_voice(text):
    # Detection for Bengali characters
    if any("\u0980" <= ch <= "\u09FF" for ch in text or ""):
        return os.getenv("EDGE_TTS_BN_VOICE", "bn-BD-NabanitaNeural")
    return os.getenv("EDGE_TTS_DEFAULT_VOICE", "en-US-EmmaMultilingualNeural")


async def generate_speech_base64(text, voice=None):
    """
    Generates an MP3 in-memory and returns it as a Base64 encoded string.
    No files are saved to the backend disk.
    """
    selected_voice = voice or choose_tts_voice(text)
    logger.info("Generating in-memory TTS | voice=%s | text_preview=%s", selected_voice, (text or "")[:50])
    
    try:
        communicate = edge_tts.Communicate(text, selected_voice)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        
        if not audio_data:
            logger.error("TTS generation returned no audio data")
            return None
            
        return {
            "base64": base64.b64encode(audio_data).decode("utf-8"),
            "voice": selected_voice
        }
    except Exception as e:
        logger.error(f"Edge TTS generation failed: {e}")
        return None


def transcribe_audio(audio_file_path):
    """
    Transcribes audio to text using Groq Whisper.
    Uses a temp file that is deleted immediately after this call in the view.
    """
    try:
        with open(audio_file_path, "rb") as file:
            transcription = client.audio.transcriptions.create(
                file=(os.path.basename(audio_file_path), file.read()),
                model="whisper-large-v3",
                response_format="json",
                language="en",
                temperature=0.0
            )
            return transcription.text
    except Exception as e:
        logger.error(f"Error transcribing audio: {e}")
        return None
