from __future__ import annotations

import csv
from io import StringIO
from typing import Any

from django.http import HttpResponse, JsonResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from audit.models import AuditEvent


class IsOwnerConsoleUser(IsAuthenticated):
    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        required_permission = required_owner_permission(request, view)
        return bool(
            super().has_permission(request, view)
            and user
            and user.is_active
            and (user.is_staff or user.is_platform_admin or user.is_superuser)
            and required_permission
            and user_has_platform_permission(user, required_permission)
        )


def required_owner_permission(request, view) -> str:
    if hasattr(view, "get_required_permission"):
        return view.get_required_permission(request)
    permission_map = getattr(view, "required_permissions", {})
    if permission_map:
        return permission_map.get(request.method, permission_map.get("*", ""))
    return getattr(view, "required_permission", "")


def user_has_platform_permission(user, permission_code: str) -> bool:
    if not permission_code:
        return False
    if getattr(user, "is_superuser", False):
        return True
    from identity.models import PlatformUserRole, RolePermission

    role_ids = PlatformUserRole.objects.filter(user=user, role__is_active=True, role__scope="PLATFORM").values_list("role_id", flat=True)
    return RolePermission.objects.filter(role_id__in=role_ids, permission__code=permission_code).exists()


def validation_error(message: str, code: str = "VALIDATION_ERROR", http_status: int = status.HTTP_400_BAD_REQUEST) -> JsonResponse:
    return JsonResponse({"error": {"code": code, "message": message}}, status=http_status)


def record_owner_audit(
    request,
    action: str,
    *,
    resource_type: str = "",
    resource_id: str = "",
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    result: str = AuditEvent.Result.SUCCESS,
    failure_reason: str = "",
) -> None:
    AuditEvent.objects.create(
        request_id=getattr(request, "request_id", ""),
        global_user_id=getattr(request.user, "id", None),
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        before_summary=before or {},
        after_summary=after or {},
        result=result,
        failure_reason=failure_reason,
        source_ip=_client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )


def csv_response(filename: str, headers: list[str], rows: list[dict[str, Any]]) -> HttpResponse:
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: sanitize_csv_value(row.get(key, "")) for key in headers})
    response = HttpResponse(buffer.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def sanitize_csv_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    if value.startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value


def bool_from_request(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on", "enabled", "active"}


def int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _client_ip(request) -> str | None:
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.META.get("REMOTE_ADDR") or None
