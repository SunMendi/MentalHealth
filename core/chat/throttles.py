import os

from rest_framework.throttling import UserRateThrottle


class ChatMessageRateThrottle(UserRateThrottle):
    scope = "chat_message"
    rate = os.getenv("CHAT_MESSAGE_RATE_LIMIT", "20/hour")
    message = "You've reached your hourly chat limit. Please try again later."


class AudioTranscriptionRateThrottle(UserRateThrottle):
    scope = "audio_transcription"
    rate = os.getenv("AUDIO_TRANSCRIPTION_RATE_LIMIT", "5/hour")
    message = "You've reached your hourly audio transcription limit. Please try again later."
