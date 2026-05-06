from rest_framework import serializers 


class CreateSessionSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    problem_category = serializers.IntegerField(required=False, allow_null=True)

class ChatMessageSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    sender = serializers.CharField()
    content = serializers.CharField()
    suggested_replies = serializers.JSONField(required=False)
    metadata = serializers.JSONField(required=False)
    created_at = serializers.DateTimeField()
    audio_url = serializers.SerializerMethodField()

    def get_audio_url(self, obj):
        return (obj.metadata or {}).get("audio_url")


class CreateMessageSerializer(serializers.Serializer):
    content = serializers.CharField()


class TextToSpeechSerializer(serializers.Serializer):
    text = serializers.CharField(allow_blank=False, trim_whitespace=True)


class CommunityPostSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    content = serializers.CharField()
    created_at = serializers.DateTimeField(read_only=True)
