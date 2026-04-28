import os
import edge_tts
from groq import Groq

# Initialize Groq client
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

async def generate_speech(text, output_path, voice="en-US-EmmaMultilingualNeural"):
    """
    Generates an MP3 file from text using Microsoft Edge TTS.
    Default voice is high quality and supportive.
    """
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)
    return output_path

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
