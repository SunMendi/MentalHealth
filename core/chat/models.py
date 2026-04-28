from django.conf import settings
from django.db import models


class ProblemCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class ClinicalProtocol(models.Model):
    category = models.OneToOneField(
        ProblemCategory, on_delete=models.CASCADE, related_name="protocol"
    )
    technique_type = models.CharField(
        max_length=50
    )  # e.g., "CBT", "DBT", "Problem Solving"
    content = models.TextField()  # The core protocol content for RAG
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.category.name} - {self.technique_type}"


class MicroAction(models.Model):
    category = models.ForeignKey(
        ProblemCategory, on_delete=models.CASCADE, related_name="micro_actions"
    )
    day_number = models.PositiveSmallIntegerField()  # 1 to 7
    title = models.CharField(max_length=200)
    description = models.TextField()

    class Meta:
        ordering = ["day_number"]
        unique_together = ["category", "day_number"]

    def __str__(self):
        return f"{self.category.name} - Day {self.day_number}: {self.title}"


class ChatSession(models.Model):
    FLOW_CHOICES = [
        ("discovery", "Discovery/Intake"),
        ("active_support", "Active Support"),
        ("crisis", "Crisis Mode"),
        ("completed", "Completed"),
    ]

    STATUS_CHOICES = [
        ("active", "Active"),
        ("closed", "Closed"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_sessions",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    current_flow = models.CharField(max_length=20, choices=FLOW_CHOICES, default="discovery")
    problem_category = models.ForeignKey(
        ProblemCategory, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title or 'Unnamed Session'} - {self.current_flow}"


class ChatMessage(models.Model):
    SENDER_CHOICES = [
        ("user", "User"),
        ("assistant", "Assistant"),
        ("system", "System"),
    ]

    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.CharField(max_length=20, choices=SENDER_CHOICES)
    content = models.TextField()
    suggested_replies = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender}: {self.content[:20]}..."


class UserPlan(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="plans"
    )
    category = models.ForeignKey(ProblemCategory, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    start_date = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.category.name} Plan"


class PlanProgress(models.Model):
    plan = models.ForeignKey(UserPlan, on_delete=models.CASCADE, related_name="progress")
    day_number = models.PositiveSmallIntegerField()
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ["plan", "day_number"]


class CommunityPost(models.Model):
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Post {self.id}: {self.content[:30]}..."