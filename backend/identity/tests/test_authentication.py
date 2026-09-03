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
from control.models import Tenant, TenantDatabase, TenantDomain, TenantMembership, TenantModule
from identity.jwt import ACCESS_COOKIE_NAME
from identity.models import MembershipRole, MfaDevice, PasswordResetToken, RecoveryCode, Role, SecuritySession, WarehouseAssignment
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


def tenant_login(client: Client, host: str, email: str, password: str, extra_payload: dict | None = None):
    payload = {"email": email, "password": password}
    if extra_payload:
        payload.update(extra_payload)
    return client.post(
        "/api/v1/auth/login/",
        payload,
        content_type="application/json",
        HTTP_HOST=host,
    )


def create_login_tenant(code: str, *, status=Tenant.Status.ACTIVE, verified=True, domain_active=True):
    tenant = Tenant.objects.create(tenant_code=code, display_name=f"Tenant {code.title()}", status=status)
    TenantDomain.objects.create(
        tenant=tenant,
        hostname=f"{code}.localhost",
        verified=verified,
        is_active=domain_active,
        is_primary=True,
        verification_method=TenantDomain.VerificationMethod.LOCAL_DEVELOPMENT,
        verified_at=timezone.now() if verified else None,
    )
    TenantDatabase.objects.create(
        tenant=tenant,
        database_alias=f"tenant_{code}",
        database_host_reference="postgres",
        database_name=f"lattice_{code}",
        runtime_role_name=f"lattice_{code}_app",
        secret_reference=f"env:TENANT_{code.upper()}_DB_PASSWORD",
        provisioning_status=TenantDatabase.ProvisioningStatus.READY,
    )
    return tenant


def test_valid_login_creates_session_and_audit_event(db):
    user = get_user_model().objects.create_user(email="owner@example.test", password="StrongerPass123!")

    response = api_login(Client(REMOTE_ADDR="127.0.0.1"), "OWNER@example.test", "StrongerPass123!")

    assert response.status_code == 200
    assert response.json()["email"] == user.email
    assert response.json()["token_type"] == "Bearer"
    assert response.json()["access_token"].count(".") == 2
    assert response.json()["refresh_token"].count(".") == 2
    assert SecuritySession.objects.filter(user=user, revoked_at__isnull=True).exists()
    assert AuditEvent.objects.filter(action="LOGIN_SUCCESS", global_user_id=user.id).exists()


def test_jwt_bearer_token_authenticates_api_without_session_cookie(db):
    user = get_user_model().objects.create_user(email="jwt-owner@example.test", password="StrongerPass123!")
    login_response = api_login(Client(), user.email, "StrongerPass123!")
    token = login_response.json()["access_token"]

    response = Client().get("/api/v1/auth/me/", HTTP_AUTHORIZATION=f"Bearer {token}")

    assert response.status_code == 200
    assert response.json()["email"] == user.email


def test_refresh_token_issues_new_access_token(db):
    user = get_user_model().objects.create_user(email="refresh@example.test", password="StrongerPass123!")
    login_response = api_login(Client(), user.email, "StrongerPass123!")
    refresh_token = login_response.json()["refresh_token"]

    response = Client().post(
        "/api/v1/auth/token/refresh/",
        {"refresh_token": refresh_token},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "Bearer"
    assert response.json()["access_token"].count(".") == 2


def test_revoked_jwt_session_cannot_access_api(db):
    user = get_user_model().objects.create_user(email="revoked-jwt@example.test", password="StrongerPass123!")
    login_response = api_login(Client(), user.email, "StrongerPass123!")
    token = login_response.json()["access_token"]
    SecuritySession.objects.filter(user=user).update(revoked_at=timezone.now(), revoke_reason="test")

    response = Client().get("/api/v1/auth/me/", HTTP_AUTHORIZATION=f"Bearer {token}")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_REVOKED"


def test_cookie_jwt_does_not_authorize_state_changing_api_without_session(db):
    user = get_user_model().objects.create_user(email="cookie-jwt@example.test", password="StrongerPass123!")
    login_response = api_login(Client(), user.email, "StrongerPass123!")
    token = login_response.json()["access_token"]
    session = SecuritySession.objects.get(user=user)
    cookie_only = Client()
    cookie_only.cookies[ACCESS_COOKIE_NAME] = token

    denied = cookie_only.post("/api/v1/auth/sessions/revoke-others/")
    allowed = Client().post("/api/v1/auth/sessions/revoke-others/", HTTP_AUTHORIZATION=f"Bearer {token}")

    assert denied.status_code in {401, 403}
    assert allowed.status_code == 204
    session.refresh_from_db()
    assert session.revoked_at is None


@override_settings(ALLOWED_HOSTS=["alpha.localhost", "beta.localhost", "gamma.localhost", "testserver"])
def test_valid_alpha_user_login_on_alpha_domain_binds_tenant_session(db):
    alpha = create_login_tenant("alpha")
    user = get_user_model().objects.create_user(email="alpha.user@example.test", password="StrongerPass123!")
    TenantMembership.objects.create(user=user, tenant=alpha, status=TenantMembership.Status.ACTIVE)
    client = Client()

    response = tenant_login(client, "alpha.localhost", user.email, "StrongerPass123!")

    assert response.status_code == 200
    session = SecuritySession.objects.get(user=user, revoked_at__isnull=True)
    assert session.tenant == alpha
    assert client.session["tenant_code"] == "alpha"
    assert AuditEvent.objects.filter(action="TENANT_LOGIN_SUCCESS", global_user_id=user.id, tenant_id=alpha.id).exists()


@override_settings(ALLOWED_HOSTS=["alpha.localhost", "testserver"])
def test_tenant_login_with_existing_session_cookie_does_not_require_csrf(db):
    alpha = create_login_tenant("alpha")
    user = get_user_model().objects.create_user(email="alpha.admin@example.test", password="StrongerPass123!")
    TenantMembership.objects.create(user=user, tenant=alpha, status=TenantMembership.Status.ACTIVE)
    client = Client(enforce_csrf_checks=True)

    assert tenant_login(client, "alpha.localhost", user.email, "StrongerPass123!").status_code == 200
    response = tenant_login(client, "alpha.localhost", user.email, "StrongerPass123!")

    assert response.status_code == 200
    assert response.json()["email"] == user.email


@override_settings(ALLOWED_HOSTS=["alpha.localhost", "testserver"])
def test_login_context_returns_safe_tenant_display_without_database_details(db):
    alpha = create_login_tenant("alpha")

    response = Client().get("/api/v1/auth/login/context/", HTTP_HOST="alpha.localhost")

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "tenant"
    assert payload["tenant"]["display_name"] == alpha.display_name
    body = response.content.decode()
    assert "database" not in body
    assert "runtime_role" not in body
    assert "secret" not in body


@override_settings(ALLOWED_HOSTS=["alpha.localhost", "beta.localhost", "gamma.localhost", "testserver"])
def test_valid_beta_user_login_on_beta_domain_binds_tenant_session(db):
    beta = create_login_tenant("beta")
    user = get_user_model().objects.create_user(email="beta.user@example.test", password="StrongerPass123!")
    TenantMembership.objects.create(user=user, tenant=beta, status=TenantMembership.Status.ACTIVE)

    response = tenant_login(Client(), "beta.localhost", user.email, "StrongerPass123!")

    assert response.status_code == 200
    assert SecuritySession.objects.get(user=user, revoked_at__isnull=True).tenant == beta


@override_settings(ALLOWED_HOSTS=["alpha.localhost", "beta.localhost", "gamma.localhost", "testserver"])
def test_beta_user_on_alpha_domain_is_denied_without_fallback(db):
    alpha = create_login_tenant("alpha")
    beta = create_login_tenant("beta")
    user = get_user_model().objects.create_user(email="beta.user@example.test", password="StrongerPass123!")
    TenantMembership.objects.create(user=user, tenant=beta, status=TenantMembership.Status.ACTIVE)

    response = tenant_login(Client(), "alpha.localhost", user.email, "StrongerPass123!")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "TENANT_MEMBERSHIP_REQUIRED"
    assert not SecuritySession.objects.filter(user=user).exists()
    assert AuditEvent.objects.filter(action="TENANT_MEMBERSHIP_DENIED", global_user_id=user.id, tenant_id=alpha.id).exists()


@override_settings(ALLOWED_HOSTS=["alpha.localhost", "beta.localhost", "gamma.localhost", "testserver"])
def test_alpha_user_on_beta_domain_is_denied_without_fallback(db):
    alpha = create_login_tenant("alpha")
    beta = create_login_tenant("beta")
    user = get_user_model().objects.create_user(email="alpha.user@example.test", password="StrongerPass123!")
    TenantMembership.objects.create(user=user, tenant=alpha, status=TenantMembership.Status.ACTIVE)

    response = tenant_login(Client(), "beta.localhost", user.email, "StrongerPass123!")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "TENANT_MEMBERSHIP_REQUIRED"
    assert not SecuritySession.objects.filter(user=user).exists()
    assert AuditEvent.objects.filter(action="TENANT_MEMBERSHIP_DENIED", global_user_id=user.id, tenant_id=beta.id).exists()


@override_settings(ALLOWED_HOSTS=["alpha.localhost", "gamma.localhost", "testserver"])
def test_unknown_domain_is_denied_for_tenant_login(db):
    user = get_user_model().objects.create_user(email="user@example.test", password="StrongerPass123!")

    response = tenant_login(Client(), "gamma.localhost", user.email, "StrongerPass123!")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "UNKNOWN_TENANT_DOMAIN"
    assert not SecuritySession.objects.filter(user=user).exists()


@override_settings(ALLOWED_HOSTS=["alpha.localhost", "testserver"])
def test_unverified_or_inactive_tenant_domain_is_denied(db):
    create_login_tenant("alpha", verified=False)
    user = get_user_model().objects.create_user(email="alpha.user@example.test", password="StrongerPass123!")

    response = tenant_login(Client(), "alpha.localhost", user.email, "StrongerPass123!")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "TENANT_DOMAIN_UNAVAILABLE"


@override_settings(ALLOWED_HOSTS=["alpha.localhost", "testserver"])
def test_suspended_tenant_domain_login_is_denied(db):
    tenant = create_login_tenant("alpha", status=Tenant.Status.SUSPENDED)
    user = get_user_model().objects.create_user(email="alpha.user@example.test", password="StrongerPass123!")
    TenantMembership.objects.create(user=user, tenant=tenant, status=TenantMembership.Status.ACTIVE)

    response = tenant_login(Client(), "alpha.localhost", user.email, "StrongerPass123!")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "TENANT_UNAVAILABLE"
    assert not SecuritySession.objects.filter(user=user).exists()


@override_settings(ALLOWED_HOSTS=["alpha.localhost", "testserver"])
def test_tenant_login_rejects_browser_supplied_database_selector(db):
    alpha = create_login_tenant("alpha")
    user = get_user_model().objects.create_user(email="alpha.user@example.test", password="StrongerPass123!")
    TenantMembership.objects.create(user=user, tenant=alpha, status=TenantMembership.Status.ACTIVE)

    response = tenant_login(Client(), "alpha.localhost", user.email, "StrongerPass123!", {"database_name": "lattice_beta"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "TENANT_ACCESS_DENIED"
    assert not SecuritySession.objects.filter(user=user).exists()


@override_settings(ALLOWED_HOSTS=["alpha.localhost", "testserver"])
def test_tenant_role_requiring_mfa_blocks_password_only_login(db):
    alpha = create_login_tenant("alpha")
    user = get_user_model().objects.create_user(email="tenant.admin@example.test", password="StrongerPass123!")
    membership = TenantMembership.objects.create(user=user, tenant=alpha, status=TenantMembership.Status.ACTIVE)
    role = Role.objects.create(code="TENANT_ADMIN", name="Tenant Admin", scope=Role.Scope.TENANT, requires_mfa=True)
    MembershipRole.objects.create(membership=membership, role=role)

    response = tenant_login(Client(), "alpha.localhost", user.email, "StrongerPass123!")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "MFA_REQUIRED"
    assert not SecuritySession.objects.filter(user=user).exists()


@override_settings(ALLOWED_HOSTS=["alpha.localhost", "beta.localhost", "testserver"])
def test_tenant_session_bound_to_alpha_cannot_access_beta_tenant_api(db):
    alpha = create_login_tenant("alpha")
    beta = create_login_tenant("beta")
    user = get_user_model().objects.create_user(email="multi@example.test", password="StrongerPass123!")
    TenantMembership.objects.create(user=user, tenant=alpha, status=TenantMembership.Status.ACTIVE)
    TenantMembership.objects.create(user=user, tenant=beta, status=TenantMembership.Status.ACTIVE)
    client = Client()
    assert tenant_login(client, "alpha.localhost", user.email, "StrongerPass123!").status_code == 200

    response = client.get("/api/v1/tenant/probe/", HTTP_HOST="beta.localhost")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "TenantResolutionError"


@override_settings(ALLOWED_HOSTS=["alpha.localhost", "beta.localhost", "testserver"])
def test_tenant_jwt_bound_to_alpha_cannot_access_beta_tenant_api(db):
    alpha = create_login_tenant("alpha")
    beta = create_login_tenant("beta")
    user = get_user_model().objects.create_user(email="jwt-multi@example.test", password="StrongerPass123!")
    TenantMembership.objects.create(user=user, tenant=alpha, status=TenantMembership.Status.ACTIVE)
    TenantMembership.objects.create(user=user, tenant=beta, status=TenantMembership.Status.ACTIVE)
    login_response = tenant_login(Client(), "alpha.localhost", user.email, "StrongerPass123!")
    token = login_response.json()["access_token"]

    response = Client().get(
        "/api/v1/tenant/probe/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_HOST="beta.localhost",
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "TenantResolutionError"


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
