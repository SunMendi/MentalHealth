import os
import logging
from tempfile import NamedTemporaryFile

import cloudinary
import cloudinary.uploader
import edge_tts
from groq import Groq

logger = logging.getLogger("chat.voice")

# Initialize Groq client
client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def choose_tts_voice(text):
    if any("\u0980" <= ch <= "\u09FF" for ch in text or ""):
        return os.getenv("EDGE_TTS_BN_VOICE", "bn-BD-NabanitaNeural")
    return os.getenv("EDGE_TTS_DEFAULT_VOICE", "en-US-EmmaMultilingualNeural")


async def generate_speech(text, output_path, voice=None):
    """
    Generates an MP3 file from text using Microsoft Edge TTS.
    Default voice is high quality and supportive.
    """
    selected_voice = voice or choose_tts_voice(text)
    communicate = edge_tts.Communicate(text, selected_voice)
    await communicate.save(output_path)
    return output_path


def _get_cloudinary_config():
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
    api_key = os.getenv("CLOUDINARY_API_KEY")
    api_secret = os.getenv("CLOUDINARY_API_SECRET")

    if cloud_name and api_key and api_secret:
        logger.info("Cloudinary config found via separate env vars | cloud_name=%s", cloud_name)
        return {
            "cloud_name": cloud_name,
            "api_key": api_key,
            "api_secret": api_secret,
        }

    cloudinary_url = os.getenv("CLOUDINARY_URL")
    if not cloudinary_url or not cloudinary_url.startswith("cloudinary://"):
        return None

    credentials_and_host = cloudinary_url[len("cloudinary://"):]
    credentials, cloud_name = credentials_and_host.split("@", 1)
    api_key, api_secret = credentials.split(":", 1)
    logger.info("Cloudinary config found via CLOUDINARY_URL | cloud_name=%s", cloud_name)
    return {
        "cloud_name": cloud_name,
        "api_key": api_key,
        "api_secret": api_secret,
    }


def upload_audio_to_cloudinary(file_path, public_id):
    config = _get_cloudinary_config()
    if not config:
        logger.error("Cloudinary config missing for audio upload")
        raise RuntimeError("Cloudinary is not configured.")

    cloudinary.config(
        cloud_name=config["cloud_name"],
        api_key=config["api_key"],
        api_secret=config["api_secret"],
        secure=True,
    )
    logger.info(
        "Uploading audio to Cloudinary | public_id=%s | cloud_name=%s | file_path=%s",
        public_id,
        config["cloud_name"],
        file_path,
    )

    payload = cloudinary.uploader.upload(
        file_path,
        public_id=public_id,
        folder="mentalhealth_tts",
        resource_type="video",
        overwrite=True,
    )
    logger.info(
        "Cloudinary upload succeeded | public_id=%s | secure_url=%s",
        public_id,
        payload.get("secure_url"),
    )
    return payload["secure_url"]


def generate_and_upload_speech(text, public_id, voice=None):
    selected_voice = voice or choose_tts_voice(text)
    logger.info(
        "Starting assistant TTS generation | public_id=%s | voice=%s | text_preview=%s",
        public_id,
        selected_voice,
        (text or "")[:80],
    )

    with NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_file:
        temp_path = tmp_file.name

    try:
        import asyncio

        asyncio.run(generate_speech(text, temp_path, selected_voice))
        logger.info("Edge TTS generation succeeded | public_id=%s | temp_path=%s", public_id, temp_path)
        audio_url = upload_audio_to_cloudinary(temp_path, public_id)
        return {
            "audio_url": audio_url,
            "voice": selected_voice,
        }
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

def transcribe_audio(audio_file_path):
    """
    Transcribes audio to text using Groq Whisper.
    """
    try:
        with open(audio_file_path, "rb") as file:
            transcription = client.audio.transcriptions.create(
                file=(audio_file_path, file.read()),
                model="whisper-large-v3",
                response_format="json",
                language="en", # You can set this to auto or specific language
                temperature=0.0
            )
            return transcription.text
    except Exception as e:
        print(f"Error transcribing audio: {e}")
        return None
