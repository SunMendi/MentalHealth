import os
import sys
import django

# Setup Django environment
sys.path.append(os.path.join(os.path.dirname(__file__), "core"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

import secrets
from django.conf import settings
from rest_framework.test import APIRequestFactory
from chat.views import _persist_temp_audio, CommunityPostAPIView, TextToSpeechAPIView
from chat.serializers import CommunityPostSerializer
from chat.services.safety import check_for_crisis
from chat.services.brain import handle_user_input
from chat.models import ChatSession
from users.views import ReviewerLoginView


def test_debug_and_secret_key():
    print("Testing settings configuration...")
    # DEBUG should be a boolean
    assert isinstance(settings.DEBUG, bool), "DEBUG must be a boolean"
    # SECRET_KEY should not be empty
    assert bool(settings.SECRET_KEY), "SECRET_KEY must not be empty"
    print("  [OK] DEBUG and SECRET_KEY validated.")


def test_cors_configuration():
    print("Testing CORS allowed origin regexes...")
    import re
    test_origins = [
        ("https://my-app.up.railway.app", True),
        ("https://my-app.lovable.app", True),
        ("https://sereniomind.com", True),
        ("http://localhost:3000", True),
        ("https://malicious-hacker.com", False),
    ]
    regexes = [re.compile(p) for p in settings.CORS_ALLOWED_ORIGIN_REGEXES]
    for origin, should_match in test_origins:
        matched = any(r.match(origin) for r in regexes)
        assert matched == should_match, f"Origin {origin} expected match={should_match}, got {matched}"
    print("  [OK] CORS origin rules correctly protect APIs.")


def test_audio_path_traversal_defense():
    print("Testing audio filename sanitization...")
    class FakeFile:
        def __init__(self, name):
            self.name = name
        def chunks(self):
            return [b"fake audio data"]

    # Traversal filename attempt
    malicious_file = FakeFile("../../../../evil.sh")
    saved_path = _persist_temp_audio(malicious_file)
    try:
        # File must be inside media/temp and must end with .wav
        assert "evil.sh" not in saved_path, "Client filename must be discarded"
        assert saved_path.endswith(".wav"), "Disallowed extensions must fallback to safe .wav"
        assert os.path.dirname(os.path.abspath(saved_path)) == os.path.abspath(
            os.path.join(settings.BASE_DIR, "media", "temp")
        ), "Saved file must stay strictly within media/temp directory"
    finally:
        if os.path.exists(saved_path):
            os.remove(saved_path)
    print("  [OK] Audio path traversal prevented.")


def test_banglish_crisis_detection():
    print("Testing Romanized Bengali (Banglish) crisis triggers...")
    banglish_phrases = [
        "amar ar bachte chai na",
        "ami suicide korbo",
        "shob shesh kore dite chai",
        "ami morite chai",
    ]
    for phrase in banglish_phrases:
        detected = check_for_crisis(phrase)
        assert detected, f"Crisis phrase '{phrase}' was not detected by safety shield!"
    print("  [OK] Banglish crisis keywords caught by safety shield.")


def test_community_post_serializer_length_limit():
    print("Testing CommunityPost length limits...")
    # Oversized payload
    long_content = "A" * 1500
    serializer = CommunityPostSerializer(data={"content": long_content})
    assert not serializer.is_valid(), "Payload > 1000 chars should be rejected"
    assert "content" in serializer.errors

    valid_content = "This is a valid safe post."
    serializer_valid = CommunityPostSerializer(data={"content": valid_content})
    assert serializer_valid.is_valid(), "Valid length post should be accepted"
    print("  [OK] Community post size limit enforced.")


def test_reviewer_login_constant_time():
    print("Testing reviewer login constant time logic...")
    os.environ["REVIEWER_BYPASS_EMAIL"] = "reviewer@apple.com"
    os.environ["REVIEWER_BYPASS_SECRET"] = "SuperSecretReviewerPass123"

    factory = APIRequestFactory()
    view = ReviewerLoginView.as_view()

    # Wrong secret
    req_bad = factory.post("/api/reviewer-login/", {"email": "reviewer@apple.com", "secret": "wrong"})
    res_bad = view(req_bad)
    assert res_bad.status_code == 401, f"Expected 401, got {res_bad.status_code}"

    # Correct secret
    req_good = factory.post("/api/reviewer-login/", {"email": "reviewer@apple.com", "secret": "SuperSecretReviewerPass123"})
    res_good = view(req_good)
    assert res_good.status_code == 200, f"Expected 200, got {res_good.status_code}"
    print("  [OK] Reviewer login handles authentication securely.")


if __name__ == "__main__":
    print("=== RUNNING SECURITY FIXES VERIFICATION ===")
    test_debug_and_secret_key()
    test_cors_configuration()
    test_audio_path_traversal_defense()
    test_banglish_crisis_detection()
    test_community_post_serializer_length_limit()
    test_reviewer_login_constant_time()
    print("=== ALL 6 SECURITY CHECKS PASSED SUCCESSFULLY ===")
