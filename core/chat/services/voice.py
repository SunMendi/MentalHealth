import os
import hashlib
import time
from tempfile import NamedTemporaryFile

import edge_tts
import requests
from groq import Groq

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
    return {
        "cloud_name": cloud_name,
        "api_key": api_key,
        "api_secret": api_secret,
    }


def upload_audio_to_cloudinary(file_path, public_id):
    config = _get_cloudinary_config()
    if not config:
        raise RuntimeError("Cloudinary is not configured.")

    timestamp = str(int(time.time()))
    params_to_sign = f"folder=mentalhealth_tts&public_id={public_id}&timestamp={timestamp}{config['api_secret']}"
    signature = hashlib.sha1(params_to_sign.encode("utf-8")).hexdigest()
    upload_url = f"https://api.cloudinary.com/v1_1/{config['cloud_name']}/video/upload"

    with open(file_path, "rb") as audio_file:
        response = requests.post(
            upload_url,
            data={
                "api_key": config["api_key"],
                "timestamp": timestamp,
                "signature": signature,
                "folder": "mentalhealth_tts",
                "public_id": public_id,
                "resource_type": "video",
            },
            files={"file": audio_file},
            timeout=30,
        )

    response.raise_for_status()
    payload = response.json()
    return payload["secure_url"]


def generate_and_upload_speech(text, public_id, voice=None):
    selected_voice = voice or choose_tts_voice(text)

    with NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_file:
        temp_path = tmp_file.name

    try:
        import asyncio

        asyncio.run(generate_speech(text, temp_path, selected_voice))
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
