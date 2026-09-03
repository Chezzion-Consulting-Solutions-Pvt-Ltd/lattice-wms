from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

import pyotp
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.core import signing
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.models import AuditEvent
from control.models import Tenant, TenantDomain, TenantMembership
from identity.audit import record_security_event
from identity.jwt import (
    REFRESH_COOKIE_NAME,
    JwtAuthenticationError,
    authenticate_token,
    build_token_pair,
    clear_token_cookies,
    issue_token_pair,
    set_token_cookies,
)
from identity.models import MfaDevice, PasswordResetToken, RecoveryCode, SecuritySession
from tenancy.exceptions import TenantResolutionError
from tenancy.resolver import normalize_hostname


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "login"

    def post(self, request):
        email = str(request.data.get("email", "")).strip().lower()
        password = str(request.data.get("password", ""))
        tenant = _resolve_login_tenant_or_none(request)
        if isinstance(tenant, Response):
            return tenant
        if _ip_throttle_exceeded(request):
            record_security_event(request, action="LOGIN_THROTTLED", result=AuditEvent.Result.DENIED, tenant_id=getattr(tenant, "id", None), failure_reason="ip_rate_limit")
            return Response({"error": {"code": "LOGIN_THROTTLED", "message": "Too many login attempts."}}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        candidate_user = get_user_model().objects.filter(email=email).first() if email else None
        if candidate_user and candidate_user.locked_until and candidate_user.locked_until > timezone.now():
            record_security_event(
                request,
                action="LOGIN_FAILED",
                result=AuditEvent.Result.DENIED,
                user_id=candidate_user.id,
                tenant_id=getattr(tenant, "id", None),
                failure_reason="account_locked",
            )
            return Response({"error": {"code": "ACCOUNT_LOCKED", "message": "Account temporarily locked."}}, status=status.HTTP_423_LOCKED)
        user = authenticate(request, username=email, password=password)
        if user is None:
            _record_failed_login(request, candidate_user)
            disabled_user = get_user_model().objects.filter(email=email, is_active=False).first()
            if disabled_user and disabled_user.check_password(password):
                record_security_event(
                    request,
                    action="LOGIN_FAILED",
                    result=AuditEvent.Result.DENIED,
                    user_id=disabled_user.id,
                    tenant_id=getattr(tenant, "id", None),
                    failure_reason="account_disabled",
                )
                return Response(
                    {"error": {"code": "ACCOUNT_DISABLED", "message": "Account disabled."}},
                    status=status.HTTP_403_FORBIDDEN,
                )
            record_security_event(request, action="LOGIN_FAILED", result=AuditEvent.Result.DENIED, tenant_id=getattr(tenant, "id", None), failure_reason="invalid_credentials")
            return Response({"error": {"code": "INVALID_LOGIN", "message": "Invalid credentials."}}, status=status.HTTP_403_FORBIDDEN)
        if not user.is_active:
            record_security_event(request, action="LOGIN_FAILED", result=AuditEvent.Result.DENIED, user_id=user.id, tenant_id=getattr(tenant, "id", None), failure_reason="account_disabled")
            return Response({"error": {"code": "ACCOUNT_DISABLED", "message": "Account disabled."}}, status=status.HTTP_403_FORBIDDEN)
        membership = _validate_tenant_membership(request, user, tenant)
        if isinstance(membership, Response):
            return membership
        device = getattr(user, "mfa_device", None)
        if _privileged_requires_mfa(user, tenant=tenant) and (device is None or not device.enabled):
            record_security_event(request, action="LOGIN_FAILED", result=AuditEvent.Result.DENIED, user_id=user.id, tenant_id=getattr(tenant, "id", None), failure_reason="mfa_required")
            return Response({"error": {"code": "MFA_REQUIRED", "message": "MFA challenge required."}}, status=status.HTTP_403_FORBIDDEN)
        if device and device.enabled:
            request.session["pending_mfa_user_id"] = str(user.id)
            if tenant is not None:
                request.session["pending_mfa_tenant_id"] = str(tenant.id)
            else:
                request.session.pop("pending_mfa_tenant_id", None)
            record_security_event(request, action="LOGIN_FAILED", result=AuditEvent.Result.DENIED, user_id=user.id, tenant_id=getattr(tenant, "id", None), failure_reason="mfa_challenge")
            return Response({"error": {"code": "MFA_REQUIRED", "message": "MFA challenge required."}}, status=status.HTTP_202_ACCEPTED)

        login(request, user)
        _bind_session_tenant(request, tenant)
        _track_session(request, user, tenant=tenant)
        tokens = issue_token_pair(request, user, tenant=tenant)
        _clear_login_failures(request, user)
        record_security_event(
            request,
            action="TENANT_LOGIN_SUCCESS" if tenant else "LOGIN_SUCCESS",
            result=AuditEvent.Result.SUCCESS,
            user_id=user.id,
            tenant_id=getattr(tenant, "id", None),
        )
        response = Response({**_serialize_user(user), **tokens})
        set_token_cookies(response, tokens)
        return response


class LoginContextView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "standard_api"

    def get(self, request):
        tenant = _resolve_login_tenant_or_none(request)
        if isinstance(tenant, Response):
            return tenant
        if tenant is None:
            return Response({"mode": "owner", "title": "Owner Console"})
        return Response(
            {
                "mode": "tenant",
                "tenant": {
                    "tenant_code": tenant.tenant_code,
                    "display_name": tenant.display_name,
                    "status": tenant.status,
                },
            }
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        jwt_session = getattr(request, "lattice_security_session", None)
        if jwt_session is not None:
            jwt_session.revoked_at = timezone.now()
            jwt_session.revoke_reason = "logout"
            jwt_session.save(update_fields=["revoked_at", "revoke_reason", "updated_at"])
        session_key = request.session.session_key
        if session_key:
            SecuritySession.objects.filter(session_key_hash=SecuritySession.hash_session_key(session_key)).update(
                revoked_at=timezone.now(),
                revoke_reason="logout",
            )
        tenant_id = getattr(jwt_session, "tenant_id", None) or request.session.get("tenant_id")
        record_security_event(request, action="TENANT_LOGOUT" if tenant_id else "LOGOUT", result=AuditEvent.Result.SUCCESS, user_id=request.user.id, tenant_id=tenant_id)
        logout(request)
        response = Response(status=status.HTTP_204_NO_CONTENT)
        clear_token_cookies(response)
        return response


class TokenRefreshView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "standard_api"

    def post(self, request):
        refresh_token = str(request.data.get("refresh_token", "")) or request.COOKIES.get(REFRESH_COOKIE_NAME, "")
        if not refresh_token:
            return Response({"error": {"code": "REFRESH_TOKEN_REQUIRED", "message": "Refresh token required."}}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            principal = authenticate_token(refresh_token, token_type="refresh", source="refresh")
        except JwtAuthenticationError as exc:
            return Response({"error": {"code": exc.code, "message": exc.message}}, status=status.HTTP_401_UNAUTHORIZED)
        tokens = build_token_pair(principal.user, refresh_jti=str(principal.payload["jti"]), tenant=principal.session.tenant)
        response = Response(tokens)
        set_token_cookies(response, tokens)
        return response


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(_serialize_user(request.user))


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "password_reset"

    def post(self, request):
        email = str(request.data.get("email", "")).strip().lower()
        user = get_user_model().objects.filter(email=email, is_active=True).first() if email else None
        if user:
            raw_token = PasswordResetToken.issue_token()
            PasswordResetToken.objects.filter(user=user, used_at__isnull=True).update(used_at=timezone.now())
            PasswordResetToken.objects.create(
                user=user,
                token_hash=PasswordResetToken.hash_token(raw_token),
                expires_at=timezone.now() + timezone.timedelta(seconds=_password_reset_expiry_seconds()),
            )
            record_security_event(request, action="PASSWORD_RESET_REQUESTED", result=AuditEvent.Result.SUCCESS, user_id=user.id)
        else:
            record_security_event(request, action="PASSWORD_RESET_REQUESTED", result=AuditEvent.Result.SUCCESS)
        return Response({"detail": "If the account exists, password reset instructions will be sent."}, status=status.HTTP_202_ACCEPTED)


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "password_reset"

    def post(self, request):
        token = str(request.data.get("token", ""))
        password = str(request.data.get("password", ""))
        token_hash = PasswordResetToken.hash_token(token) if token else ""
        reset = PasswordResetToken.objects.select_related("user").filter(token_hash=token_hash).first()
        if not reset or reset.used_at or reset.expires_at <= timezone.now() or not reset.user.is_active:
            record_security_event(request, action="PASSWORD_RESET_FAILED", result=AuditEvent.Result.DENIED, failure_reason="invalid_or_expired_token")
            return Response({"error": {"code": "INVALID_RESET_TOKEN", "message": "Invalid or expired reset token."}}, status=status.HTTP_403_FORBIDDEN)
        try:
            validate_password(password, user=reset.user)
        except ValidationError as exc:
            return Response({"error": {"code": "INVALID_PASSWORD", "message": " ".join(exc.messages)}}, status=status.HTTP_400_BAD_REQUEST)

        reset.user.set_password(password)
        reset.user.failed_login_count = 0
        reset.user.locked_until = None
        reset.user.save(update_fields=["password", "password_changed_at", "failed_login_count", "locked_until", "updated_at"])
        reset.used_at = timezone.now()
        reset.save(update_fields=["used_at", "updated_at"])
        SecuritySession.objects.filter(user=reset.user, revoked_at__isnull=True).update(
            revoked_at=timezone.now(),
            revoke_reason="password_reset",
        )
        record_security_event(request, action="PASSWORD_RESET_COMPLETED", result=AuditEvent.Result.SUCCESS, user_id=reset.user.id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SessionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sessions = request.user.security_sessions.order_by("-last_seen_at")
        return Response(
            {
                "sessions": [
                    {
                        "id": str(session.id),
                        "created_at": session.created_at.isoformat(),
                        "last_seen_at": session.last_seen_at.isoformat(),
                        "expires_at": session.expires_at.isoformat(),
                        "revoked_at": session.revoked_at.isoformat() if session.revoked_at else None,
                    }
                    for session in sessions
                ]
            }
        )


class RevokeSessionView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, session_id):
        updated = request.user.security_sessions.filter(id=session_id, revoked_at__isnull=True).update(
            revoked_at=timezone.now(),
            revoke_reason="user_revoked",
        )
        if updated:
            record_security_event(request, action="SESSION_REVOKED", result=AuditEvent.Result.SUCCESS, user_id=request.user.id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class RevokeOtherSessionsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        current_hash = _current_security_session_hash(request)
        request.user.security_sessions.exclude(session_key_hash=current_hash).filter(revoked_at__isnull=True).update(
            revoked_at=timezone.now(),
            revoke_reason="user_revoked_others",
        )
        record_security_event(request, action="SESSION_REVOKED", result=AuditEvent.Result.SUCCESS, user_id=request.user.id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MfaSetupView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        secret = pyotp.random_base32()
        device, _ = MfaDevice.objects.update_or_create(
            user=request.user,
            defaults={"secret_reference": _protect_secret(secret), "enabled": False, "confirmed_at": None},
        )
        record_security_event(request, action="MFA_SETUP_STARTED", result=AuditEvent.Result.SUCCESS, user_id=request.user.id)
        return Response(
            {
                "device_id": device.id,
                "manual_entry_key": secret,
                "provisioning_uri": pyotp.totp.TOTP(secret).provisioning_uri(
                    name=request.user.email,
                    issuer_name="Lattice",
                ),
            }
        )


class MfaVerifyView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        user = request.user if getattr(request.user, "is_authenticated", False) else _pending_mfa_user(request)
        if user is None:
            return Response({"error": {"code": "MFA_CONTEXT_REQUIRED", "message": "MFA context required."}}, status=status.HTTP_403_FORBIDDEN)
        device = getattr(user, "mfa_device", None)
        code = str(request.data.get("code", "")).strip()
        recovery_code = str(request.data.get("recovery_code", "")).strip()
        verified = _verify_totp(device, code) if device else False
        if not verified and recovery_code:
            verified = _consume_recovery_code(user, recovery_code)
        if not verified:
            record_security_event(request, action="MFA_VERIFY_FAILED", result=AuditEvent.Result.DENIED, user_id=user.id)
            return Response({"error": {"code": "INVALID_MFA_CODE", "message": "Invalid MFA code."}}, status=status.HTTP_403_FORBIDDEN)

        if device and not device.enabled:
            device.enabled = True
            device.confirmed_at = timezone.now()
            device.save(update_fields=["enabled", "confirmed_at", "updated_at"])
        if not getattr(request.user, "is_authenticated", False):
            tenant = _pending_mfa_tenant(request)
            membership = _validate_tenant_membership(request, user, tenant)
            if isinstance(membership, Response):
                return membership
            login(request, user)
            _bind_session_tenant(request, tenant)
            _track_session(request, user, tenant=tenant)
            tokens = issue_token_pair(request, user, tenant=tenant)
            request.session.pop("pending_mfa_user_id", None)
            request.session.pop("pending_mfa_tenant_id", None)
        record_security_event(request, action="MFA_VERIFIED", result=AuditEvent.Result.SUCCESS, user_id=user.id, tenant_id=request.session.get("tenant_id"))
        response_payload = _serialize_user(user)
        if "tokens" in locals():
            response_payload.update(tokens)
        response = Response(response_payload)
        if "tokens" in locals():
            set_token_cookies(response, tokens)
        return response


class MfaDisableView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        password = str(request.data.get("password", ""))
        if not request.user.check_password(password):
            return Response({"error": {"code": "REAUTH_REQUIRED", "message": "Re-authentication required."}}, status=status.HTTP_403_FORBIDDEN)
        MfaDevice.objects.filter(user=request.user).update(enabled=False, confirmed_at=None)
        record_security_event(request, action="MFA_DISABLED", result=AuditEvent.Result.SUCCESS, user_id=request.user.id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class RecoveryCodeRegenerateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        RecoveryCode.objects.filter(user=request.user, used_at__isnull=True).delete()
        codes = [secrets.token_urlsafe(9) for _ in range(8)]
        RecoveryCode.objects.bulk_create([RecoveryCode(user=request.user, code_hash=make_password(code)) for code in codes])
        record_security_event(request, action="MFA_RECOVERY_REGENERATED", result=AuditEvent.Result.SUCCESS, user_id=request.user.id)
        return Response({"recovery_codes": codes})


def _serialize_user(user) -> dict[str, object]:
    data = {
        "id": str(user.id),
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "is_staff": user.is_staff,
        "is_platform_admin": user.is_platform_admin,
    }
    return data


def _track_session(request, user, *, tenant: Tenant | None = None) -> None:
    if not request.session.session_key:
        request.session.save()
    session_key = request.session.session_key
    expiry_age = request.session.get_expiry_age()
    SecuritySession.objects.update_or_create(
        session_key_hash=SecuritySession.hash_session_key(session_key),
        defaults={
            "user": user,
            "tenant": tenant,
            "expires_at": timezone.now() + timezone.timedelta(seconds=expiry_age),
            "ip_address": request.META.get("REMOTE_ADDR"),
            "user_agent": request.META.get("HTTP_USER_AGENT", "")[:1000],
        },
    )


def _current_security_session_hash(request) -> str:
    jwt_session = getattr(request, "lattice_security_session", None)
    if jwt_session is not None:
        return jwt_session.session_key_hash
    return SecuritySession.hash_session_key(request.session.session_key or "")


def _privileged_requires_mfa(user, *, tenant: Tenant | None = None) -> bool:
    if user.is_platform_admin or user.is_superuser:
        return True
    if tenant is not None:
        return user.memberships.filter(tenant=tenant, role_assignments__role__requires_mfa=True).exists()
    return user.memberships.filter(role_assignments__role__requires_mfa=True).exists()


def _protect_secret(secret: str) -> str:
    nonce = secrets.token_bytes(16)
    key = _mfa_encryption_key()
    plaintext = secret.encode("utf-8")
    keystream = _key_stream(key, nonce, len(plaintext))
    ciphertext = bytes(byte ^ keystream[index] for index, byte in enumerate(plaintext))
    tag = hmac.new(key, nonce + ciphertext, hashlib.sha256).digest()
    return "enc:v1:" + ":".join(
        base64.urlsafe_b64encode(part).decode("ascii").rstrip("=")
        for part in (nonce, ciphertext, tag)
    )


def _unprotect_secret(reference: str) -> str:
    if reference.startswith("enc:v1:"):
        _, _, nonce_part, ciphertext_part, tag_part = reference.split(":", 4)
        nonce = _b64decode(nonce_part)
        ciphertext = _b64decode(ciphertext_part)
        tag = _b64decode(tag_part)
        key = _mfa_encryption_key()
        expected = hmac.new(key, nonce + ciphertext, hashlib.sha256).digest()
        if not hmac.compare_digest(tag, expected):
            raise ValueError("Invalid MFA secret envelope.")
        keystream = _key_stream(key, nonce, len(ciphertext))
        return bytes(byte ^ keystream[index] for index, byte in enumerate(ciphertext)).decode("utf-8")
    if not reference.startswith("signed:"):
        raise ValueError("Unsupported MFA secret reference.")
    return signing.loads(reference.removeprefix("signed:"), salt="lattice-mfa")


def _verify_totp(device: MfaDevice | None, code: str) -> bool:
    if device is None or not code:
        return False
    return pyotp.TOTP(_unprotect_secret(device.secret_reference)).verify(code, valid_window=1)


def _pending_mfa_user(request):
    user_id = request.session.get("pending_mfa_user_id")
    if not user_id:
        return None
    return get_user_model().objects.filter(id=user_id, is_active=True).first()


def _pending_mfa_tenant(request):
    tenant_id = request.session.get("pending_mfa_tenant_id")
    if not tenant_id:
        return None
    return Tenant.objects.filter(id=tenant_id, status=Tenant.Status.ACTIVE).first()


def _bind_session_tenant(request, tenant: Tenant | None) -> None:
    if tenant is None:
        request.session.pop("tenant_id", None)
        request.session.pop("tenant_code", None)
        return
    request.session["tenant_id"] = str(tenant.id)
    request.session["tenant_code"] = tenant.tenant_code


def _resolve_login_tenant_or_none(request):
    try:
        _reject_login_database_selector_attempts(request)
    except TenantResolutionError:
        record_security_event(request, action="TENANT_ACCESS_DENIED", result=AuditEvent.Result.DENIED, failure_reason="client_supplied_database_selector")
        return Response({"error": {"code": "TENANT_ACCESS_DENIED", "message": "Tenant access denied."}}, status=status.HTTP_403_FORBIDDEN)

    hostname = normalize_hostname(request.get_host())
    domain = TenantDomain.objects.select_related("tenant").filter(hostname=hostname).first()
    if domain is None:
        if hostname in _owner_hosts():
            return None
        record_security_event(request, action="TENANT_ACCESS_DENIED", result=AuditEvent.Result.DENIED, failure_reason="unknown_tenant_domain")
        return Response({"error": {"code": "UNKNOWN_TENANT_DOMAIN", "message": "Tenant access denied."}}, status=status.HTTP_403_FORBIDDEN)
    if not domain.verified or not domain.is_active:
        record_security_event(request, action="TENANT_ACCESS_DENIED", result=AuditEvent.Result.DENIED, tenant_id=domain.tenant_id, failure_reason="domain_not_verified_or_inactive")
        return Response({"error": {"code": "TENANT_DOMAIN_UNAVAILABLE", "message": "Tenant access denied."}}, status=status.HTTP_403_FORBIDDEN)
    if domain.tenant.status != Tenant.Status.ACTIVE:
        record_security_event(request, action="TENANT_ACCESS_DENIED", result=AuditEvent.Result.DENIED, tenant_id=domain.tenant_id, failure_reason="tenant_not_active")
        return Response({"error": {"code": "TENANT_UNAVAILABLE", "message": "Tenant access denied."}}, status=status.HTTP_403_FORBIDDEN)
    return domain.tenant


def _validate_tenant_membership(request, user, tenant: Tenant | None):
    if tenant is None:
        return None
    membership = TenantMembership.objects.filter(user=user, tenant=tenant).first()
    if membership is None:
        record_security_event(request, action="TENANT_MEMBERSHIP_DENIED", result=AuditEvent.Result.DENIED, user_id=user.id, tenant_id=tenant.id, failure_reason="missing_membership")
        return Response({"error": {"code": "TENANT_MEMBERSHIP_REQUIRED", "message": "Tenant access denied."}}, status=status.HTTP_403_FORBIDDEN)
    if membership.status != TenantMembership.Status.ACTIVE:
        record_security_event(request, action="TENANT_MEMBERSHIP_DENIED", result=AuditEvent.Result.DENIED, user_id=user.id, tenant_id=tenant.id, failure_reason="membership_not_active")
        return Response({"error": {"code": "TENANT_MEMBERSHIP_INACTIVE", "message": "Tenant access denied."}}, status=status.HTTP_403_FORBIDDEN)
    return membership


def _reject_login_database_selector_attempts(request) -> None:
    from tenancy.resolver import UNTRUSTED_DB_HEADERS, UNTRUSTED_DB_QUERY_KEYS

    query_keys = {key.lower() for key in request.GET.keys()}
    body_keys = {str(key).lower() for key in getattr(request, "data", {}).keys()}
    if query_keys & UNTRUSTED_DB_QUERY_KEYS or body_keys & UNTRUSTED_DB_QUERY_KEYS:
        raise TenantResolutionError("Client-supplied database selectors are not allowed.")
    if any(header in request.META for header in UNTRUSTED_DB_HEADERS):
        raise TenantResolutionError("Client-supplied tenant database headers are not allowed.")


def _owner_hosts() -> set[str]:
    configured = getattr(settings, "LATTICE_OWNER_HOSTS", "")
    return {normalize_hostname(host) for host in str(configured).split(",") if host.strip()}


def _consume_recovery_code(user, raw_code: str) -> bool:
    for recovery_code in RecoveryCode.objects.filter(user=user, used_at__isnull=True):
        if check_password(raw_code, recovery_code.code_hash):
            recovery_code.used_at = timezone.now()
            recovery_code.save(update_fields=["used_at", "updated_at"])
            return True
    return False


def _password_reset_expiry_seconds() -> int:
    return int(getattr(settings, "PASSWORD_RESET_TOKEN_SECONDS", 3600))


def _ip_throttle_exceeded(request) -> bool:
    limit = int(getattr(settings, "LOGIN_IP_FAILURE_LIMIT", 20))
    key = f"login:ip:{_cache_key_part(request.META.get('REMOTE_ADDR') or 'unknown')}"
    count = cache.get(key, 0)
    return count >= limit


def _record_failed_login(request, user) -> None:
    _record_ip_failure(request)
    if user is None:
        return
    failures = user.failed_login_count + 1
    user.failed_login_count = failures
    if failures >= int(getattr(settings, "LOGIN_USER_LOCKOUT_FAILURES", 5)):
        user.locked_until = timezone.now() + timezone.timedelta(seconds=int(getattr(settings, "LOGIN_USER_LOCKOUT_SECONDS", 900)))
    user.save(update_fields=["failed_login_count", "locked_until", "updated_at"])
    record_security_event(request, action="SUSPICIOUS_LOGIN", result=AuditEvent.Result.DENIED, user_id=user.id, failure_reason="failed_password")


def _clear_login_failures(request, user) -> None:
    user.failed_login_count = 0
    user.locked_until = None
    user.save(update_fields=["failed_login_count", "locked_until", "last_login", "updated_at"])
    cache.delete(f"login:ip:{_cache_key_part(request.META.get('REMOTE_ADDR') or 'unknown')}")


def _cache_key_part(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _record_ip_failure(request) -> None:
    window = int(getattr(settings, "LOGIN_FAILURE_WINDOW_SECONDS", 300))
    key = f"login:ip:{_cache_key_part(request.META.get('REMOTE_ADDR') or 'unknown')}"
    cache.set(key, cache.get(key, 0) + 1, window)


def _mfa_encryption_key() -> bytes:
    configured = getattr(settings, "MFA_SECRET_ENCRYPTION_KEY", "") or settings.SECRET_KEY
    return hashlib.sha256(str(configured).encode("utf-8")).digest()


def _key_stream(key: bytes, nonce: bytes, size: int) -> bytes:
    blocks: list[bytes] = []
    counter = 0
    while sum(len(block) for block in blocks) < size:
        blocks.append(hmac.new(key, nonce + counter.to_bytes(4, "big"), hashlib.sha256).digest())
        counter += 1
    return b"".join(blocks)[:size]


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
