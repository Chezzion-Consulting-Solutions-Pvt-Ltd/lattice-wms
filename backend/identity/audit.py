from __future__ import annotations

from audit.models import AuditEvent


def record_security_event(request, *, action: str, result: str, user_id=None, tenant_id=None, failure_reason: str = "") -> None:
    AuditEvent.objects.create(
        request_id=getattr(request, "request_id", ""),
        tenant_id=tenant_id,
        global_user_id=user_id,
        source_ip=_client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:1000],
        action=action,
        resource_type="identity",
        result=result,
        failure_reason=failure_reason,
    )


def _client_ip(request) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.META.get("REMOTE_ADDR")
