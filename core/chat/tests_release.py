from importlib import import_module
from types import SimpleNamespace
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connection
from django.urls import reverse
from django.test import override_settings
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken
from .models import (
    AppVersionConfig, CommunityPost, CommunityPostReport, MicroAction,
    ProblemCategory, SpecialistWaitlistRegistration, UserPlan,
)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ReleaseIntegrationTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="release-test", password="test-password")
        self.other = get_user_model().objects.create_user(username="other-test", password="test-password")
        self.client.force_authenticate(self.user)

    def test_waitlist_is_persisted_idempotent_and_account_owned(self):
        url = reverse("specialist-waitlist")
        self.assertEqual(self.client.get(url).data, {"registered": False, "registration": None})
        data = {"name": "Test", "contact": "test@example.com", "focus": "Anxiety & Panic"}
        self.assertEqual(self.client.post(url, data, format="json").status_code, 200)
        data["name"] = "Updated"
        self.assertEqual(self.client.post(url, data, format="json").status_code, 200)
        self.assertEqual(SpecialistWaitlistRegistration.objects.count(), 1)
        self.assertEqual(self.client.get(url).data["registration"]["name"], "Updated")
        self.client.force_authenticate(self.other)
        self.assertFalse(self.client.get(url).data["registered"])
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertEqual(SpecialistWaitlistRegistration.objects.count(), 1)
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertEqual(SpecialistWaitlistRegistration.objects.count(), 0)

    def test_waitlist_validates_contact_focus_and_auth(self):
        url = reverse("specialist-waitlist")
        data = {"name": "Test", "contact": "invalid", "focus": "Anxiety & Panic"}
        self.assertEqual(self.client.post(url, data, format="json").status_code, 400)
        data.update(contact="test@example.com", focus="invented")
        self.assertEqual(self.client.post(url, data, format="json").status_code, 400)
        self.client.force_authenticate(None)
        for method in (self.client.get, self.client.post, self.client.delete):
            self.assertEqual(method(url).status_code, 401)

    def test_reports_persist_without_removing_another_users_feed(self):
        post = CommunityPost.objects.create(content="A quiet reflection")
        url = reverse("community-post-report", args=[post.id])
        self.assertEqual(self.client.post(url, {}, format="json").status_code, 200)
        self.assertEqual(self.client.post(url, {}, format="json").status_code, 200)
        self.assertEqual(CommunityPostReport.objects.count(), 1)
        self.assertEqual(self.client.get(reverse("community-posts")).data, [])
        self.client.force_authenticate(self.other)
        self.assertEqual(len(self.client.get(reverse("community-posts")).data), 1)
        self.assertEqual(self.client.post(reverse("community-post-report", args=[9999]), {}).status_code, 404)

    def test_reports_require_auth_and_validate_reason(self):
        post = CommunityPost.objects.create(content="A reflection")
        url = reverse("community-post-report", args=[post.id])
        self.assertEqual(self.client.post(url, {"reason": "x" * 1001}, format="json").status_code, 400)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.post(url, {}).status_code, 401)

    def test_categories_are_real_ids_with_complete_plans_and_daily_contract(self):
        category = ProblemCategory.objects.create(id=57, name="A seeded category", description="Description")
        ProblemCategory.objects.create(id=99, name="Incomplete")
        for day in range(1, 8):
            MicroAction.objects.create(category=category, day_number=day, title=f"Day {day}", description="Gentle task")
        response = self.client.get(reverse("plan-categories"))
        self.assertEqual(response.data, [{"id": 57, "name": category.name, "description": category.description}])
        self.assertEqual(self.client.post(reverse("activate-plan", args=[99])).status_code, 404)
        self.assertEqual(UserPlan.objects.count(), 0)
        self.assertEqual(self.client.post(reverse("activate-plan", args=[57])).status_code, 200)
        task = self.client.get(reverse("daily-plan"))
        self.assertEqual(task.status_code, 200)
        self.assertEqual((task.data["category"], task.data["category_id"], task.data["total_days"]), (category.name, 57, 7))
        self.assertEqual(self.client.post(reverse("daily-plan")).status_code, 200)
        self.assertEqual(self.client.get(reverse("daily-plan")).data["day"], 2)
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(reverse("daily-plan")).status_code, 404)

    def test_refresh_endpoint_recovers_access_and_rejects_invalid_refresh(self):
        self.client.force_authenticate(None)
        refresh = RefreshToken.for_user(self.user)
        response = self.client.post(reverse("token-refresh"), {"refresh": str(refresh)}, format="json")
        self.assertEqual(response.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        self.assertEqual(self.client.get(reverse("user-profile")).status_code, 200)
        self.client.credentials()
        self.assertEqual(self.client.post(reverse("token-refresh"), {"refresh": "invalid"}, format="json").status_code, 401)

    def test_version_seed_is_safe_idempotent_and_no_forced_update(self):
        seed = import_module("chat.migrations.0006_seed_release_version_config").seed_release_versions
        config = AppVersionConfig.objects.get(platform="android")
        config.latest_version = "2.0.0"
        config.save()
        editor = SimpleNamespace(connection=connection)
        seed(apps, editor)
        seed(apps, editor)
        self.assertEqual(AppVersionConfig.objects.get(platform="android").latest_version, "2.0.0")
        self.assertEqual(AppVersionConfig.objects.count(), 2)
        response = self.client.get(reverse("app-version-check"), {"platform": "ios", "version": "1.0.0"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["force_update"])
        self.assertFalse(response.data["update_required"])
