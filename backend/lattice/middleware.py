"""Request middleware for Lattice."""
from __future__ import annotations

import uuid
from collections.abc import Callable

from django.contrib.auth import logout
from django.http import HttpRequest, HttpResponse
from django.http import JsonResponse
from django.utils import timezone

from identity.models import SecuritySession


class RequestIDMiddleware:
    """Attach a stable request ID to every request and response."""

    header_name = "HTTP_X_REQUEST_ID"
    response_header = "X-Request-ID"

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request_id = request.META.get(self.header_name) or str(uuid.uuid4())
        request.request_id = request_id
        response = self.get_response(request)
        response[self.response_header] = request_id
        return response


class SecuritySessionMiddleware:
    """Enforce Lattice's authoritative security session registry for APIs."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if self._requires_enforcement(request):
            session_key = request.session.session_key
            if not session_key:
                logout(request)
                return self._denied("SESSION_REQUIRED", "Authenticated session required.", 401)
            session_hash = SecuritySession.hash_session_key(session_key)
            tracked = SecuritySession.objects.filter(session_key_hash=session_hash, user=request.user).first()
            if tracked is None:
                logout(request)
                return self._denied("SESSION_UNTRACKED", "Session is not active.", 401)
            if tracked.revoked_at:
                logout(request)
                return self._denied("SESSION_REVOKED", "Session has been revoked.", 401)
            if tracked.expires_at <= timezone.now():
                tracked.revoked_at = timezone.now()
                tracked.revoke_reason = "expired"
                tracked.save(update_fields=["revoked_at", "revoke_reason", "updated_at"])
                logout(request)
                return self._denied("SESSION_EXPIRED", "Session has expired.", 401)
            tracked.last_seen_at = timezone.now()
            tracked.save(update_fields=["last_seen_at", "updated_at"])
        return self.get_response(request)

    def _requires_enforcement(self, request: HttpRequest) -> bool:
        user = getattr(request, "user", None)
        return bool(
            request.path.startswith("/api/")
            and user
            and user.is_authenticated
            and not request.path.startswith("/api/v1/auth/mfa/verify/")
        )

    def _denied(self, code: str, message: str, status_code: int) -> JsonResponse:
        return JsonResponse({"error": {"code": code, "message": message}}, status=status_code)
