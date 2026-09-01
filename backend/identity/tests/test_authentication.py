from __future__ import annotations

from unittest.mock import patch

from django.core.cache import cache
from django.contrib.auth import get_user_model
import pyotp
import pytest
from django.test import Client
from django.test import override_settings
from django.utils import timezone

from audit.models import AuditEvent
from identity.models import MfaDevice, PasswordResetToken, RecoveryCode, SecuritySession
from identity.views import _protect_secret, _unprotect_secret


@pytest.fixture(autouse=True)
def clear_auth_rate_limits():
    cache.clear()
    yield
    cache.clear()


def api_login(client: Client, email: str, password: str):
    return client.post(
        "/api/v1/auth/login/",
        {"email": email, "password": password},
        content_type="application/json",
    )


def test_valid_login_creates_session_and_audit_event(db):
    user = get_user_model().objects.create_user(email="owner@example.test", password="StrongerPass123!")

    response = api_login(Client(REMOTE_ADDR="127.0.0.1"), "OWNER@example.test", "StrongerPass123!")

    assert response.status_code == 200
    assert response.json()["email"] == user.email
    assert SecuritySession.objects.filter(user=user, revoked_at__isnull=True).exists()
    assert AuditEvent.objects.filter(action="LOGIN_SUCCESS", global_user_id=user.id).exists()


def test_invalid_password_is_denied_and_audited_without_password(db):
    get_user_model().objects.create_user(email="owner@example.test", password="StrongerPass123!")

    response = Client(REMOTE_ADDR="127.0.0.1").post(
        "/api/v1/auth/login/",
        {"email": "owner@example.test", "password": "wrong-secret"},
        content_type="application/json",
    )

    assert response.status_code == 403
    event = AuditEvent.objects.get(action="LOGIN_FAILED")
    assert event.failure_reason == "invalid_credentials"
    assert "wrong-secret" not in str(event.before_summary)
    assert "wrong-secret" not in str(event.after_summary)


def test_disabled_account_is_denied(db):
    get_user_model().objects.create_user(email="disabled@example.test", password="StrongerPass123!", is_active=False)

    response = Client().post(
        "/api/v1/auth/login/",
        {"email": "disabled@example.test", "password": "StrongerPass123!"},
        content_type="application/json",
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACCOUNT_DISABLED"


def test_logout_revokes_tracked_session(db):
    client = Client()
    user = get_user_model().objects.create_user(email="owner@example.test", password="StrongerPass123!")
    assert api_login(client, user.email, "StrongerPass123!").status_code == 200
    session = SecuritySession.objects.get(user=user)

    response = client.post("/api/v1/auth/logout/")

    assert response.status_code == 204
    session.refresh_from_db()
    assert session.revoked_at is not None


def test_mfa_enrollment_and_verification(db):
    client = Client()
    user = get_user_model().objects.create_user(email="mfa@example.test", password="StrongerPass123!")
    assert api_login(client, user.email, "StrongerPass123!").status_code == 200

    setup = client.post("/api/v1/auth/mfa/setup/")
    assert setup.status_code == 200
    secret = setup.json()["manual_entry_key"]
    verify = client.post("/api/v1/auth/mfa/verify/", {"code": pyotp.TOTP(secret).now()}, content_type="application/json")

    assert verify.status_code == 200
    device = MfaDevice.objects.get(user=user)
    assert device.enabled
    assert secret not in device.secret_reference
    assert device.secret_reference.startswith("enc:v1:")
    assert _unprotect_secret(device.secret_reference) == secret


def test_mfa_challenge_and_invalid_code(db):
    client = Client()
    user = get_user_model().objects.create_user(email="mfa@example.test", password="StrongerPass123!")
    secret = pyotp.random_base32()
    MfaDevice.objects.create(user=user, secret_reference=_protect_secret(secret), enabled=True)

    login_response = client.post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": "StrongerPass123!"},
        content_type="application/json",
    )
    invalid_response = client.post("/api/v1/auth/mfa/verify/", {"code": "000000"}, content_type="application/json")

    assert login_response.status_code == 202
    assert login_response.json()["error"]["code"] == "MFA_REQUIRED"
    assert invalid_response.status_code == 403


def test_recovery_code_single_use(db):
    client = Client()
    user = get_user_model().objects.create_user(email="recovery@example.test", password="StrongerPass123!")
    assert api_login(client, user.email, "StrongerPass123!").status_code == 200
    response = client.post("/api/v1/auth/mfa/recovery/regenerate/")
    raw_code = response.json()["recovery_codes"][0]
    client.logout()
    session = client.session
    session["pending_mfa_user_id"] = str(user.id)
    session.save()

    first = client.post("/api/v1/auth/mfa/verify/", {"recovery_code": raw_code}, content_type="application/json")
    client.logout()
    session = client.session
    session["pending_mfa_user_id"] = str(user.id)
    session.save()
    second = client.post("/api/v1/auth/mfa/verify/", {"recovery_code": raw_code}, content_type="application/json")

    assert first.status_code == 200
    assert second.status_code == 403
    assert RecoveryCode.objects.get(user=user, used_at__isnull=False)


def test_privileged_role_requires_mfa(db):
    user = get_user_model().objects.create_user(
        email="platform-admin@example.test",
        password="StrongerPass123!",
        is_platform_admin=True,
    )

    response = Client().post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": "StrongerPass123!"},
        content_type="application/json",
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "MFA_REQUIRED"


def test_password_reset_request_is_generic_and_does_not_enumerate_users(db):
    get_user_model().objects.create_user(email="owner@example.test", password="StrongerPass123!")

    with patch("identity.models.PasswordResetToken.issue_token", return_value="reset-token-value"):
        known = Client().post(
            "/api/v1/auth/password/reset/request/",
            {"email": "owner@example.test"},
            content_type="application/json",
        )
    unknown = Client().post(
        "/api/v1/auth/password/reset/request/",
        {"email": "missing@example.test"},
        content_type="application/json",
    )

    assert known.status_code == 202
    assert unknown.status_code == 202
    assert known.json() == unknown.json()
    token = PasswordResetToken.objects.get()
    assert token.token_hash == PasswordResetToken.hash_token("reset-token-value")
    assert "reset-token-value" not in str(AuditEvent.objects.filter(action="PASSWORD_RESET_REQUESTED").values())


def test_password_reset_confirm_is_one_time_and_revokes_sessions(db):
    client = Client()
    user = get_user_model().objects.create_user(email="reset@example.test", password="StrongerPass123!")
    assert api_login(client, user.email, "StrongerPass123!").status_code == 200
    session = SecuritySession.objects.get(user=user, revoked_at__isnull=True)
    with patch("identity.models.PasswordResetToken.issue_token", return_value="reset-token-value"):
        Client().post(
            "/api/v1/auth/password/reset/request/",
            {"email": user.email},
            content_type="application/json",
        )

    confirm = Client().post(
        "/api/v1/auth/password/reset/confirm/",
        {"token": "reset-token-value", "password": "NewStrongerPass123!"},
        content_type="application/json",
    )
    reuse = Client().post(
        "/api/v1/auth/password/reset/confirm/",
        {"token": "reset-token-value", "password": "AnotherStrongPass123!"},
        content_type="application/json",
    )
    session.refresh_from_db()
    user.refresh_from_db()

    assert confirm.status_code == 204
    assert reuse.status_code == 403
    assert user.check_password("NewStrongerPass123!")
    assert session.revoked_at is not None
    assert PasswordResetToken.objects.get().used_at is not None
    assert client.get("/api/v1/auth/me/").status_code in {401, 403}


def test_expired_password_reset_token_is_denied(db):
    user = get_user_model().objects.create_user(email="expired@example.test", password="StrongerPass123!")
    token = "expired-reset-token"
    PasswordResetToken.objects.create(
        user=user,
        token_hash=PasswordResetToken.hash_token(token),
        expires_at=timezone.now() - timezone.timedelta(seconds=1),
    )

    response = Client().post(
        "/api/v1/auth/password/reset/confirm/",
        {"token": token, "password": "NewStrongerPass123!"},
        content_type="application/json",
    )

    assert response.status_code == 403


@override_settings(LOGIN_USER_LOCKOUT_FAILURES=2, LOGIN_USER_LOCKOUT_SECONDS=1, LOGIN_IP_FAILURE_LIMIT=20)
def test_failed_login_lockout_and_recovery(db):
    cache.clear()
    user = get_user_model().objects.create_user(email="locked@example.test", password="StrongerPass123!")
    client = Client(REMOTE_ADDR="127.0.0.7")

    assert api_login(client, user.email, "wrong-password").status_code == 403
    assert api_login(client, user.email, "wrong-password").status_code == 403
    locked = api_login(client, user.email, "StrongerPass123!")
    user.refresh_from_db()

    assert locked.status_code == 423
    assert user.failed_login_count == 2
    assert user.locked_until is not None

    user.locked_until = timezone.now() - timezone.timedelta(seconds=1)
    user.save(update_fields=["locked_until", "updated_at"])
    recovered = api_login(client, user.email, "StrongerPass123!")
    user.refresh_from_db()

    assert recovered.status_code == 200
    assert user.failed_login_count == 0
    assert user.locked_until is None
    assert AuditEvent.objects.filter(action="SUSPICIOUS_LOGIN", global_user_id=user.id).exists()


@override_settings(LOGIN_IP_FAILURE_LIMIT=2)
def test_login_ip_rate_limit(db):
    cache.clear()
    client = Client(REMOTE_ADDR="127.0.0.8")

    assert api_login(client, "missing1@example.test", "bad-password").status_code == 403
    assert api_login(client, "missing2@example.test", "bad-password").status_code == 403
    throttled = api_login(client, "missing3@example.test", "bad-password")

    assert throttled.status_code == 429


def test_revoked_session_cannot_access_api(db):
    client = Client()
    user = get_user_model().objects.create_user(email="revoked@example.test", password="StrongerPass123!")
    assert api_login(client, user.email, "StrongerPass123!").status_code == 200
    SecuritySession.objects.filter(user=user).update(revoked_at=timezone.now(), revoke_reason="test")

    response = client.get("/api/v1/auth/me/")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_REVOKED"


def test_expired_session_cannot_access_api(db):
    client = Client()
    user = get_user_model().objects.create_user(email="expired-session@example.test", password="StrongerPass123!")
    assert api_login(client, user.email, "StrongerPass123!").status_code == 200
    SecuritySession.objects.filter(user=user).update(expires_at=timezone.now() - timezone.timedelta(seconds=1))

    response = client.get("/api/v1/auth/me/")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_EXPIRED"


def test_revoke_one_and_other_sessions_enforced_with_real_requests(db):
    user = get_user_model().objects.create_user(email="sessions@example.test", password="StrongerPass123!")
    first = Client()
    second = Client()
    assert api_login(first, user.email, "StrongerPass123!").status_code == 200
    assert api_login(second, user.email, "StrongerPass123!").status_code == 200
    first_session = SecuritySession.objects.get(session_key_hash=SecuritySession.hash_session_key(first.session.session_key))
    second_session = SecuritySession.objects.get(session_key_hash=SecuritySession.hash_session_key(second.session.session_key))

    assert first.delete(f"/api/v1/auth/sessions/{second_session.id}/").status_code == 204
    assert second.get("/api/v1/auth/me/").status_code == 401
    assert first.get("/api/v1/auth/me/").status_code == 200

    second = Client()
    assert api_login(second, user.email, "StrongerPass123!").status_code == 200
    assert second.post("/api/v1/auth/sessions/revoke-others/").status_code == 204

    assert first.get("/api/v1/auth/me/").status_code == 401
    assert second.get("/api/v1/auth/me/").status_code == 200
