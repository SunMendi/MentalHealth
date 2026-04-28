from rest_framework import serializers 


class CreateSessionSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=40, required=False, allow_blank=True)

class ChatMessageSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    sender = serializers.CharField()
    content = serializers.CharField()
    suggested_replies = serializers.JSONField(required=False)
    metadata = serializers.JSONField(required=False)
    created_at = serializers.DateTimeField()


class CreateMessageSerializer(serializers.Serializer):
    content = serializers.CharField()


class CommunityPostSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    content = serializers.CharField()
    created_at = serializers.DateTimeField(read_only=True)
