from __future__ import annotations

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.views import APIView

from control.api.common import IsOwnerConsoleUser, record_owner_audit, validation_error
from control.api.serializers import notification_summary, setting_summary
from control.models import OwnerNotification, PlatformSetting


SAFE_SETTING_KEYS = {
    "general",
    "security",
    "authentication",
    "provisioning",
    "notifications",
    "domains",
    "backup-retention",
    "support-access",
    "branding",
}


class OwnerSettingsView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]

    def get(self, request):
        ensure_default_settings()
        return JsonResponse({"settings": [setting_summary(setting) for setting in PlatformSetting.objects.order_by("key")]})

    def patch(self, request):
        key = str(request.data.get("key", "")).strip().lower()
        if key not in SAFE_SETTING_KEYS:
            return validation_error("Unsupported platform setting key.")
        value = request.data.get("value")
        if not isinstance(value, dict):
            return validation_error("Platform setting value must be an object.")
        if contains_unsafe_branding(value):
            return validation_error("Branding settings cannot include arbitrary CSS or JavaScript.", "UNSAFE_BRANDING")
        setting, _created = PlatformSetting.objects.update_or_create(key=key, defaults={"value": value, "description": str(request.data.get("description", "")).strip()})
        record_owner_audit(request, "SETTINGS_UPDATED", resource_type="PlatformSetting", resource_id=setting.key, after=setting_summary(setting))
        return JsonResponse({"setting": setting_summary(setting)})


class OwnerNotificationsView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]

    def get(self, request):
        notifications = OwnerNotification.objects.order_by("-created_at")[:100]
        return JsonResponse({"notifications": [notification_summary(notification) for notification in notifications], "unread": OwnerNotification.objects.filter(read_at__isnull=True).count()})


class OwnerNotificationReadView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]

    def post(self, request, notification_id):
        notification = get_object_or_404(OwnerNotification, id=notification_id)
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at", "updated_at"])
        return JsonResponse({"notification": notification_summary(notification)})


class OwnerNotificationsMarkAllReadView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]

    def post(self, request):
        OwnerNotification.objects.filter(read_at__isnull=True).update(read_at=timezone.now())
        return JsonResponse({"unread": 0})


def ensure_default_settings() -> None:
    defaults = {
        "general": {"platform_display_name": "Lattice", "default_timezone": "UTC", "default_language": "en"},
        "security": {"mfa_required_for_privileged_users": True, "session_timeout_minutes": 60, "failed_login_threshold": 5, "support_access_max_hours": 24},
        "authentication": {"password_policy": "strong", "mfa_policy": "privileged-required"},
        "provisioning": {"default_region": "us-east-1", "default_timezone": "UTC", "default_migration_policy": "manual"},
        "notifications": {"email_enabled": False},
        "domains": {"base_domain": ""},
        "backup-retention": {"provider": "NOT_CONFIGURED", "retention_days": 30},
        "support-access": {"max_duration_hours": 24, "approval_required": True},
        "branding": {"platform_display_name": "Lattice"},
    }
    for key, value in defaults.items():
        PlatformSetting.objects.get_or_create(key=key, defaults={"value": value})


def contains_unsafe_branding(value: dict) -> bool:
    serialized_keys = " ".join(str(key).lower() for key in value.keys())
    return "css" in serialized_keys or "javascript" in serialized_keys or "script" in serialized_keys
