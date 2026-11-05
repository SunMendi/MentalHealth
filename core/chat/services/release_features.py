"""Account-owned support registration and moderation persistence."""
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from ..models import CommunityPost, CommunityPostReport, SpecialistWaitlistRegistration


def save_waitlist_registration(user, data):
    try:
        with transaction.atomic():
            registration, _ = SpecialistWaitlistRegistration.objects.update_or_create(user=user, defaults=data)
        return registration
    except IntegrityError as exc:
        raise ValidationError({"detail": "Could not save your registration. Please try again."}) from exc


def report_community_post(user, post_id, reason):
    post = get_object_or_404(CommunityPost, id=post_id)
    try:
        with transaction.atomic():
            report, _ = CommunityPostReport.objects.get_or_create(user=user, post=post, defaults={"reason": reason})
        return report
    except IntegrityError as exc:
        raise ValidationError({"detail": "Could not submit this report. Please try again."}) from exc


def cancel_waitlist_registration(user):
    SpecialistWaitlistRegistration.objects.filter(user=user).delete()
