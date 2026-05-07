from rest_framework import serializers 
import re


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


VERSION_PATTERN = re.compile(r"^\d+(\.\d+){0,2}$")


class AppVersionCheckSerializer(serializers.Serializer):
    platform = serializers.ChoiceField(choices=["android", "ios"])
    version = serializers.CharField()

    def validate_version(self, value):
        normalized = value.strip()
        if not VERSION_PATTERN.match(normalized):
            raise serializers.ValidationError("Version must look like 1.0.0")
        return normalized


class AppVersionConfigSerializer(serializers.Serializer):
    platform = serializers.ChoiceField(choices=["android", "ios"])
    latest_version = serializers.CharField()
    minimum_supported_version = serializers.CharField()
    force_update = serializers.BooleanField(required=False, default=False)
    update_message = serializers.CharField(required=False, allow_blank=True, default="")
    store_url = serializers.URLField(required=False, allow_blank=True, default="")

    def validate_latest_version(self, value):
        normalized = value.strip()
        if not VERSION_PATTERN.match(normalized):
            raise serializers.ValidationError("Version must look like 1.0.0")
        return normalized

    def validate_minimum_supported_version(self, value):
        normalized = value.strip()
        if not VERSION_PATTERN.match(normalized):
            raise serializers.ValidationError("Version must look like 1.0.0")
        return normalized

    def validate(self, attrs):
        latest_parts = [int(part) for part in attrs["latest_version"].split(".")]
        minimum_parts = [int(part) for part in attrs["minimum_supported_version"].split(".")]
        max_len = max(len(latest_parts), len(minimum_parts))
        latest_parts.extend([0] * (max_len - len(latest_parts)))
        minimum_parts.extend([0] * (max_len - len(minimum_parts)))
        if minimum_parts > latest_parts:
            raise serializers.ValidationError(
                {"minimum_supported_version": "Minimum supported version cannot be greater than latest version."}
            )
        return attrs


class CommunityPostSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    content = serializers.CharField()
    created_at = serializers.DateTimeField(read_only=True)
