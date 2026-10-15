import os
from rest_framework.throttling import SimpleRateThrottle


class ChatMessageRateThrottle(SimpleRateThrottle):
    scope = "chat_message"
    rate = os.getenv("CHAT_MESSAGE_RATE_LIMIT", "30/hour")
    message = "You are sending messages too fast. Please take a breath and try again later."

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return f"throttle_user_chat_{request.user.id}"
        return f"throttle_ip_chat_{self.get_ident(request)}"


class AudioTranscriptionRateThrottle(SimpleRateThrottle):
    scope = "audio_transcription"
    rate = os.getenv("AUDIO_TRANSCRIPTION_RATE_LIMIT", "10/hour")
    message = "You have reached your audio transcription limit. Please try again later."

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return f"throttle_user_audio_{request.user.id}"
        return f"throttle_ip_audio_{self.get_ident(request)}"

