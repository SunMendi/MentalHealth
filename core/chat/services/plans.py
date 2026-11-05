from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from ..models import UserPlan, PlanProgress, MicroAction, ProblemCategory

TOTAL_PLAN_DAYS = 7


def available_plan_categories():
    # Do not offer a category that would produce missing daily tasks.
    return ProblemCategory.objects.annotate(
        task_days=Count("micro_actions", filter=Q(micro_actions__day_number__gte=1, micro_actions__day_number__lte=TOTAL_PLAN_DAYS))
    ).filter(task_days=TOTAL_PLAN_DAYS).order_by("name", "id")


def activate_plan(user, category_id):
    category = get_object_or_404(available_plan_categories(), id=category_id)
    try:
        with transaction.atomic():
            # Serialize activation for this account, including concurrent requests.
            type(user).objects.select_for_update().get(pk=user.pk)
            UserPlan.objects.filter(user=user, is_active=True).update(is_active=False)
            plan = UserPlan.objects.create(user=user, category=category)
            PlanProgress.objects.bulk_create([PlanProgress(plan=plan, day_number=i) for i in range(1, TOTAL_PLAN_DAYS + 1)])
        return plan
    except IntegrityError as exc:
        raise ValidationError({"detail": "Could not activate this plan. Please try again."}) from exc


def get_current_plan(user):
    return UserPlan.objects.filter(user=user, is_active=True).select_related("category").first()


def get_daily_task(user):
    plan = get_current_plan(user)
    if not plan:
        return None
    progress = PlanProgress.objects.filter(plan=plan, is_completed=False).order_by("day_number").first()
    if not progress:
        return None
    task = MicroAction.objects.filter(category=plan.category, day_number=progress.day_number).first()
    return {
        "task": task, "day": progress.day_number, "is_completed": progress.is_completed,
        "category": plan.category.name, "category_id": plan.category_id,
        "total_days": plan.progress.count(),
    }


def complete_daily_task(user):
    with transaction.atomic():
        type(user).objects.select_for_update().get(pk=user.pk)
        plan = get_current_plan(user)
        if not plan:
            return False
        progress = PlanProgress.objects.filter(plan=plan, is_completed=False).order_by("day_number").first()
        if progress:
            progress.is_completed = True
            progress.completed_at = timezone.now()
            progress.save(update_fields=["is_completed", "completed_at"])
            return True
    return False
