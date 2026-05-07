from django.contrib import admin
from .models import AppVersionConfig


@admin.register(AppVersionConfig)
class AppVersionConfigAdmin(admin.ModelAdmin):
    list_display = ("platform", "latest_version", "minimum_supported_version", "force_update", "updated_at")
    search_fields = ("platform", "latest_version", "minimum_supported_version")
