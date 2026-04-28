from datetime import datetime
from ..models import UserPlan, PlanProgress, MicroAction, ProblemCategory

def activate_plan(user, category_id):
    """
    Starts a 7-day plan for a specific category.
    """
    category = ProblemCategory.objects.get(id=category_id)
    
    # Deactivate existing plan for this user (if any)
    UserPlan.objects.filter(user=user, is_active=True).update(is_active=False)
    
    plan = UserPlan.objects.create(user=user, category=category)
    
    # Create empty progress for 7 days
    for i in range(1, 8):
        PlanProgress.objects.create(plan=plan, day_number=i)
        
    return plan

def get_current_plan(user):
    return UserPlan.objects.filter(user=user, is_active=True).first()

def get_daily_task(user):
    """
    Returns the MicroAction for the user's current day in their active plan.
    """
    plan = get_current_plan(user)
    if not plan:
        return None
        
    # Find the first incomplete day
    progress = PlanProgress.objects.filter(plan=plan, is_completed=False).order_by('day_number').first()
    if not progress:
        return None
        
    task = MicroAction.objects.filter(category=plan.category, day_number=progress.day_number).first()
    return {
        "task": task,
        "day": progress.day_number,
        "is_completed": progress.is_completed
    }

def complete_daily_task(user):
    plan = get_current_plan(user)
    if not plan:
        return False
        
    progress = PlanProgress.objects.filter(plan=plan, is_completed=False).order_by('day_number').first()
    if progress:
        progress.is_completed = True
        progress.completed_at = datetime.now()
        progress.save()
        return True
    return False
