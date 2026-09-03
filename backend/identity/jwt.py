from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.utils import timezone
from rest_framework import authentication, exceptions

from identity.models import SecuritySession


ACCESS_COOKIE_NAME = "lattice_access"
REFRESH_COOKIE_NAME = "lattice_refresh"
ALGORITHM = "HS256"


@dataclass(frozen=True)
class JwtPrincipal:
    user: Any
    session: SecuritySession
    payload: dict[str, Any]
    source: str


class JwtAuthenticationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class LatticeJWTAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        if getattr(request, "lattice_jwt_principal", None) is not None:
            principal = request.lattice_jwt_principal
            return principal.user, principal.payload
        if getattr(request, "lattice_skip_cookie_jwt", False):
            return None

        token, source = get_request_token(request)
        if not token:
            return None

        try:
            principal = authenticate_token(token, token_type="access", source=source)
        except JwtAuthenticationError as exc:
            raise exceptions.AuthenticationFailed({"code": exc.code, "message": exc.message}) from exc

        request.lattice_jwt_principal = principal
        request.lattice_security_session = principal.session
        return principal.user, principal.payload


def get_request_token(request) -> tuple[str, str]:
    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip(), "authorization"
    cookie_token = request.COOKIES.get(ACCESS_COOKIE_NAME, "")
    if cookie_token:
        return cookie_token, "cookie"
    return "", ""


def authenticate_token(token: str, *, token_type: str, source: str = "authorization") -> JwtPrincipal:
    payload = decode_token(token)
    if payload.get("typ") != token_type:
        raise JwtAuthenticationError("INVALID_TOKEN_TYPE", "Invalid token type.")
    jti = str(payload.get("jti", ""))
    user_id = str(payload.get("sub", ""))
    if not jti or not user_id:
        raise JwtAuthenticationError("INVALID_TOKEN", "Invalid token.")
    user = get_user_model().objects.filter(id=user_id, is_active=True).first()
    if user is None:
        raise JwtAuthenticationError("USER_INACTIVE", "User is inactive.")
    tracked = SecuritySession.objects.filter(jwt_token_hash=SecuritySession.hash_session_key(jti), user=user).first()
    if tracked is None:
        raise JwtAuthenticationError("SESSION_UNTRACKED", "Session is not active.")
    if tracked.revoked_at:
        raise JwtAuthenticationError("SESSION_REVOKED", "Session has been revoked.")
    if tracked.expires_at <= timezone.now():
        tracked.revoked_at = timezone.now()
        tracked.revoke_reason = "expired"
        tracked.save(update_fields=["revoked_at", "revoke_reason", "updated_at"])
        raise JwtAuthenticationError("SESSION_EXPIRED", "Session has expired.")
    tracked.last_seen_at = timezone.now()
    tracked.save(update_fields=["last_seen_at", "updated_at"])
    return JwtPrincipal(user=user, session=tracked, payload=payload, source=source)


def issue_token_pair(request, user, *, tenant=None) -> dict[str, Any]:
    refresh_jti = secrets.token_urlsafe(32)
    now = timezone.now()
    refresh_expires_at = now + timezone.timedelta(seconds=refresh_token_lifetime_seconds())
    session_key = request.session.session_key
    if not session_key:
        request.session.save()
        session_key = request.session.session_key
    SecuritySession.objects.update_or_create(
        session_key_hash=SecuritySession.hash_session_key(session_key),
        defaults={
            "jwt_token_hash": SecuritySession.hash_session_key(refresh_jti),
            "user": user,
            "tenant": tenant,
            "expires_at": refresh_expires_at,
            "ip_address": request.META.get("REMOTE_ADDR"),
            "user_agent": request.META.get("HTTP_USER_AGENT", "")[:1000],
        },
    )
    return build_token_pair(user, refresh_jti=refresh_jti, tenant=tenant)


def build_token_pair(user, *, refresh_jti: str, tenant=None) -> dict[str, Any]:
    return {
        "access_token": encode_token(user, refresh_jti=refresh_jti, token_type="access", lifetime_seconds=access_token_lifetime_seconds(), tenant=tenant),
        "refresh_token": encode_token(user, refresh_jti=refresh_jti, token_type="refresh", lifetime_seconds=refresh_token_lifetime_seconds(), tenant=tenant),
        "token_type": "Bearer",
        "expires_in": access_token_lifetime_seconds(),
    }


def encode_token(user, *, refresh_jti: str, token_type: str, lifetime_seconds: int, tenant=None) -> str:
    now = timezone.now()
    payload: dict[str, Any] = {
        "iss": getattr(settings, "JWT_ISSUER", "lattice"),
        "aud": getattr(settings, "JWT_AUDIENCE", "lattice-api"),
        "sub": str(user.id),
        "jti": refresh_jti,
        "typ": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + timezone.timedelta(seconds=lifetime_seconds)).timestamp()),
    }
    if tenant is not None:
        payload["tenant_id"] = str(tenant.id)
        payload["tenant_code"] = tenant.tenant_code
    return _sign(payload)


def decode_token(token: str) -> dict[str, Any]:
    try:
        header_part, payload_part, signature_part = token.split(".")
    except ValueError as exc:
        raise JwtAuthenticationError("INVALID_TOKEN", "Invalid token.") from exc

    signed = f"{header_part}.{payload_part}".encode("ascii")
    expected = _b64encode(hmac.new(_jwt_key(), signed, hashlib.sha256).digest())
    if not hmac.compare_digest(signature_part, expected):
        raise JwtAuthenticationError("INVALID_TOKEN", "Invalid token.")
    header = _json_loads(header_part)
    if header.get("alg") != ALGORITHM:
        raise JwtAuthenticationError("INVALID_TOKEN", "Invalid token.")
    payload = _json_loads(payload_part)
    if payload.get("iss") != getattr(settings, "JWT_ISSUER", "lattice"):
        raise JwtAuthenticationError("INVALID_TOKEN", "Invalid token issuer.")
    if payload.get("aud") != getattr(settings, "JWT_AUDIENCE", "lattice-api"):
        raise JwtAuthenticationError("INVALID_TOKEN", "Invalid token audience.")
    if int(payload.get("exp", 0)) <= int(timezone.now().timestamp()):
        raise JwtAuthenticationError("TOKEN_EXPIRED", "Token has expired.")
    return payload


def set_token_cookies(response, tokens: dict[str, Any]) -> None:
    secure = bool(getattr(settings, "JWT_COOKIE_SECURE", not settings.DEBUG))
    same_site = getattr(settings, "JWT_COOKIE_SAMESITE", "Lax")
    response.set_cookie(
        ACCESS_COOKIE_NAME,
        tokens["access_token"],
        max_age=access_token_lifetime_seconds(),
        httponly=True,
        secure=secure,
        samesite=same_site,
    )
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        tokens["refresh_token"],
        max_age=refresh_token_lifetime_seconds(),
        httponly=True,
        secure=secure,
        samesite=same_site,
    )


def clear_token_cookies(response) -> None:
    response.delete_cookie(ACCESS_COOKIE_NAME)
    response.delete_cookie(REFRESH_COOKIE_NAME)


def access_token_lifetime_seconds() -> int:
    return int(getattr(settings, "JWT_ACCESS_TOKEN_SECONDS", 900))


def refresh_token_lifetime_seconds() -> int:
    return int(getattr(settings, "JWT_REFRESH_TOKEN_SECONDS", 604800))


def jwt_error_response(code: str, message: str, status_code: int = 401) -> JsonResponse:
    return JsonResponse({"error": {"code": code, "message": message}}, status=status_code)


def _sign(payload: dict[str, Any]) -> str:
    header = {"alg": ALGORITHM, "typ": "JWT"}
    header_part = _b64encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_part = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signed = f"{header_part}.{payload_part}".encode("ascii")
    signature = _b64encode(hmac.new(_jwt_key(), signed, hashlib.sha256).digest())
    return f"{header_part}.{payload_part}.{signature}"


def _json_loads(value: str) -> dict[str, Any]:
    try:
        return json.loads(_b64decode(value))
    except (ValueError, json.JSONDecodeError) as exc:
        raise JwtAuthenticationError("INVALID_TOKEN", "Invalid token.") from exc


def _jwt_key() -> bytes:
    configured = getattr(settings, "JWT_SIGNING_KEY", "") or settings.SECRET_KEY
    return hashlib.sha256(str(configured).encode("utf-8")).digest()


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
