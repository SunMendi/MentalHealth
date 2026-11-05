from django.contrib import admin
from .models import AppVersionConfig


@admin.register(AppVersionConfig)
class AppVersionConfigAdmin(admin.ModelAdmin):
    list_display = ("platform", "latest_version", "minimum_supported_version", "force_update", "updated_at")
    search_fields = ("platform", "latest_version", "minimum_supported_version")


from .models import CommunityPostReport, SpecialistWaitlistRegistration


@admin.register(SpecialistWaitlistRegistration)
class SpecialistWaitlistRegistrationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "name", "contact", "focus", "created_at")
    search_fields = ("name", "contact", "user__username")
    list_filter = ("focus",)


@admin.register(CommunityPostReport)
class CommunityPostReportAdmin(admin.ModelAdmin):
    list_display = ("id", "post_id", "user", "reviewed", "created_at")
    list_filter = ("reviewed",)
    search_fields = ("reason",)
    actions = ("mark_reviewed",)

    @admin.action(description="Mark selected reports reviewed")
    def mark_reviewed(self, request, queryset):
        queryset.update(reviewed=True)
