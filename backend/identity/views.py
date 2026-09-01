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
from identity.audit import record_security_event
from identity.models import MfaDevice, PasswordResetToken, RecoveryCode, SecuritySession


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "login"

    def post(self, request):
        email = str(request.data.get("email", "")).strip().lower()
        password = str(request.data.get("password", ""))
        if _ip_throttle_exceeded(request):
            record_security_event(request, action="LOGIN_THROTTLED", result=AuditEvent.Result.DENIED, failure_reason="ip_rate_limit")
            return Response({"error": {"code": "LOGIN_THROTTLED", "message": "Too many login attempts."}}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        candidate_user = get_user_model().objects.filter(email=email).first() if email else None
        if candidate_user and candidate_user.locked_until and candidate_user.locked_until > timezone.now():
            record_security_event(
                request,
                action="LOGIN_FAILED",
                result=AuditEvent.Result.DENIED,
                user_id=candidate_user.id,
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
                    failure_reason="account_disabled",
                )
                return Response(
                    {"error": {"code": "ACCOUNT_DISABLED", "message": "Account disabled."}},
                    status=status.HTTP_403_FORBIDDEN,
                )
            record_security_event(request, action="LOGIN_FAILED", result=AuditEvent.Result.DENIED, failure_reason="invalid_credentials")
            return Response({"error": {"code": "INVALID_LOGIN", "message": "Invalid credentials."}}, status=status.HTTP_403_FORBIDDEN)
        if not user.is_active:
            record_security_event(request, action="LOGIN_FAILED", result=AuditEvent.Result.DENIED, user_id=user.id, failure_reason="account_disabled")
            return Response({"error": {"code": "ACCOUNT_DISABLED", "message": "Account disabled."}}, status=status.HTTP_403_FORBIDDEN)
        device = getattr(user, "mfa_device", None)
        if _privileged_requires_mfa(user) and (device is None or not device.enabled):
            record_security_event(request, action="LOGIN_FAILED", result=AuditEvent.Result.DENIED, user_id=user.id, failure_reason="mfa_required")
            return Response({"error": {"code": "MFA_REQUIRED", "message": "MFA challenge required."}}, status=status.HTTP_403_FORBIDDEN)
        if device and device.enabled:
            request.session["pending_mfa_user_id"] = str(user.id)
            record_security_event(request, action="LOGIN_FAILED", result=AuditEvent.Result.DENIED, user_id=user.id, failure_reason="mfa_challenge")
            return Response({"error": {"code": "MFA_REQUIRED", "message": "MFA challenge required."}}, status=status.HTTP_202_ACCEPTED)

        login(request, user)
        _track_session(request, user)
        _clear_login_failures(request, user)
        record_security_event(request, action="LOGIN_SUCCESS", result=AuditEvent.Result.SUCCESS, user_id=user.id)
        return Response(_serialize_user(user))


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        session_key = request.session.session_key
        if session_key:
            SecuritySession.objects.filter(session_key_hash=SecuritySession.hash_session_key(session_key)).update(
                revoked_at=timezone.now(),
                revoke_reason="logout",
            )
        record_security_event(request, action="LOGOUT", result=AuditEvent.Result.SUCCESS, user_id=request.user.id)
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


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
        current_hash = SecuritySession.hash_session_key(request.session.session_key or "")
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
            login(request, user)
            _track_session(request, user)
            request.session.pop("pending_mfa_user_id", None)
        record_security_event(request, action="MFA_VERIFIED", result=AuditEvent.Result.SUCCESS, user_id=user.id)
        return Response(_serialize_user(user))


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
    return {
        "id": str(user.id),
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "is_staff": user.is_staff,
        "is_platform_admin": user.is_platform_admin,
    }


def _track_session(request, user) -> None:
    if not request.session.session_key:
        request.session.save()
    session_key = request.session.session_key
    expiry_age = request.session.get_expiry_age()
    SecuritySession.objects.update_or_create(
        session_key_hash=SecuritySession.hash_session_key(session_key),
        defaults={
            "user": user,
            "expires_at": timezone.now() + timezone.timedelta(seconds=expiry_age),
            "ip_address": request.META.get("REMOTE_ADDR"),
            "user_agent": request.META.get("HTTP_USER_AGENT", "")[:1000],
        },
    )


def _privileged_requires_mfa(user) -> bool:
    if user.is_platform_admin or user.is_superuser:
        return True
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
