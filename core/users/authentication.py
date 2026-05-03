import hashlib
import logging

from django.conf import settings
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken


logger = logging.getLogger("users.auth")


def _fingerprint(value):
    if not value:
        return "missing"
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


class LoggingJWTAuthentication(JWTAuthentication):
    def get_validated_token(self, raw_token):
        try:
            return super().get_validated_token(raw_token)
        except InvalidToken as exc:
            logger.error(
                "JWT validation failed: %s | signing_key_fp=%s | algorithm=%s | header_types=%s | token_prefix=%s",
                exc,
                _fingerprint(settings.SIMPLE_JWT.get("SIGNING_KEY")),
                settings.SIMPLE_JWT.get("ALGORITHM"),
                settings.SIMPLE_JWT.get("AUTH_HEADER_TYPES"),
                str(raw_token)[:16],
            )
            raise
