from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView

from control.api.common import IsOwnerConsoleUser, bool_from_request, record_owner_audit, validation_error
from control.api.serializers import permission_summary, role_summary, session_summary, support_access_summary, user_summary
from control.models import Tenant
from identity.models import PasswordResetToken, Permission, PlatformTenantAccessGrant, PlatformUserRole, Role, RolePermission, SecuritySession


class OwnerPlatformUserListCreateView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]
    required_permissions = {"GET": "platform.users.view", "POST": "platform.users.manage"}

    def get(self, request):
        users = filter_platform_users(request)
        page, paginator, page_size = paginate_queryset(request, users)
        return JsonResponse({"users": [user_summary(user) for user in page.object_list], "pagination": pagination_summary(page, paginator, page_size)})

    def post(self, request):
        email = str(request.data.get("email", "")).strip().lower()
        if not email:
            return validation_error("Email is required.")
        try:
            user = get_user_model().objects.create_user(
                email=email,
                first_name=str(request.data.get("first_name", "")).strip(),
                last_name=str(request.data.get("last_name", "")).strip(),
                is_staff=bool_from_request(request.data.get("is_staff"), True),
                is_platform_admin=bool_from_request(request.data.get("is_platform_admin"), False),
                mfa_required=bool_from_request(request.data.get("mfa_required"), True),
            )
            replace_platform_roles(user, request.data.get("platform_roles", []))
        except IntegrityError:
            return validation_error("A platform user with this email already exists.", "USER_CONFLICT", status.HTTP_409_CONFLICT)
        record_owner_audit(request, "PLATFORM_USER_CREATED", resource_type="GlobalUser", resource_id=str(user.id), after=user_summary(user))
        return JsonResponse({"user": user_summary(user)}, status=status.HTTP_201_CREATED)


class OwnerPlatformUserDetailView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]
    required_permissions = {"GET": "platform.users.view", "PATCH": "platform.users.manage"}

    def get(self, request, user_id):
        return JsonResponse({"user": user_summary(get_object_or_404(get_user_model(), id=user_id))})

    def patch(self, request, user_id):
        user = get_object_or_404(get_user_model(), id=user_id)
        before = user_summary(user)
        for field in ["first_name", "last_name"]:
            if field in request.data:
                setattr(user, field, str(request.data.get(field, "")).strip())
        for field in ["is_active", "is_staff", "is_platform_admin", "mfa_required"]:
            if field in request.data:
                setattr(user, field, bool_from_request(request.data.get(field), getattr(user, field)))
        user.save()
        if "platform_roles" in request.data:
            before_roles = set(user_summary(user)["platform_roles"])
            replace_platform_roles(user, request.data.get("platform_roles", []))
            if before_roles != set(user_summary(user)["platform_roles"]):
                record_owner_audit(request, "PLATFORM_USER_ROLE_CHANGED", resource_type="GlobalUser", resource_id=str(user.id), before=before, after=user_summary(user))
        record_owner_audit(request, "PLATFORM_USER_UPDATED" if user.is_active else "PLATFORM_USER_DISABLED", resource_type="GlobalUser", resource_id=str(user.id), before=before, after=user_summary(user))
        return JsonResponse({"user": user_summary(user)})


class OwnerPlatformUserActionView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]
    required_permission = "platform.users.manage"

    def post(self, request, user_id, action):
        user = get_object_or_404(get_user_model(), id=user_id)
        before = user_summary(user)
        if action == "activate":
            user.is_active = True
            user.save(update_fields=["is_active", "updated_at"])
            audit_action = "PLATFORM_USER_ACTIVATED"
        elif action == "disable":
            if would_disable_last_platform_admin(user):
                return validation_error("At least one active Platform Admin must remain.", "LAST_PLATFORM_ADMIN_PROTECTED", status.HTTP_409_CONFLICT)
            user.is_active = False
            user.save(update_fields=["is_active", "updated_at"])
            SecuritySession.objects.filter(user=user, revoked_at__isnull=True).update(revoked_at=timezone.now(), revoke_reason="platform_user_disabled")
            audit_action = "PLATFORM_USER_DISABLED"
        elif action == "revoke-sessions":
            SecuritySession.objects.filter(user=user, revoked_at__isnull=True).update(revoked_at=timezone.now(), revoke_reason="owner_revoked_all")
            audit_action = "SESSION_REVOKED"
        elif action == "password-reset":
            token = PasswordResetToken.issue_token()
            PasswordResetToken.objects.filter(user=user, used_at__isnull=True).update(used_at=timezone.now())
            PasswordResetToken.objects.create(user=user, token_hash=PasswordResetToken.hash_token(token), expires_at=timezone.now() + timezone.timedelta(hours=1))
            audit_action = "PASSWORD_RESET_REQUESTED"
        else:
            return validation_error("Unsupported platform user action.", "UNKNOWN_ACTION", status.HTTP_404_NOT_FOUND)
        record_owner_audit(request, audit_action, resource_type="GlobalUser", resource_id=str(user.id), before=before, after=user_summary(user))
        return JsonResponse({"user": user_summary(user)})


class OwnerPlatformUserRoleView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]
    required_permission = "platform.users.manage"

    def post(self, request, user_id):
        user = get_object_or_404(get_user_model(), id=user_id)
        role = get_object_or_404(Role, id=request.data.get("role_id"), scope=Role.Scope.PLATFORM, is_active=True)
        before = user_summary(user)
        PlatformUserRole.objects.get_or_create(user=user, role=role)
        if role.code == "PLATFORM_ADMIN":
            user.is_staff = True
            user.is_platform_admin = True
            user.mfa_required = True
            user.save(update_fields=["is_staff", "is_platform_admin", "mfa_required", "updated_at"])
        record_owner_audit(request, "PLATFORM_USER_ROLE_CHANGED", resource_type="GlobalUser", resource_id=str(user.id), before=before, after=user_summary(user))
        return JsonResponse({"user": user_summary(user)})

    def delete(self, request, user_id):
        user = get_object_or_404(get_user_model(), id=user_id)
        role = get_object_or_404(Role, id=request.data.get("role_id"), scope=Role.Scope.PLATFORM)
        if role.code == "PLATFORM_ADMIN" and would_disable_last_platform_admin(user):
            return validation_error("At least one active Platform Admin must remain.", "LAST_PLATFORM_ADMIN_PROTECTED", status.HTTP_409_CONFLICT)
        before = user_summary(user)
        PlatformUserRole.objects.filter(user=user, role=role).delete()
        record_owner_audit(request, "PLATFORM_USER_ROLE_CHANGED", resource_type="GlobalUser", resource_id=str(user.id), before=before, after=user_summary(user))
        return JsonResponse({"user": user_summary(user)})


class OwnerRoleListCreateView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]
    required_permissions = {"GET": "platform.roles.view", "POST": "platform.roles.manage"}

    def get(self, request):
        ensure_default_roles()
        roles = filter_roles(request)
        page, paginator, page_size = paginate_queryset(request, roles)
        return JsonResponse({"roles": [role_summary(role) for role in page.object_list], "pagination": pagination_summary(page, paginator, page_size)})

    def post(self, request):
        code = str(request.data.get("code", "")).strip().upper()
        name = str(request.data.get("name", "")).strip()
        if not code or not name:
            return validation_error("Role code and name are required.")
        if Role.objects.filter(code=code).exists():
            return validation_error("Role code must be unique.", "ROLE_CONFLICT", status.HTTP_409_CONFLICT)
        try:
            role = Role.objects.create(code=code, name=name, scope=str(request.data.get("scope", Role.Scope.PLATFORM)), is_active=bool_from_request(request.data.get("is_active"), True), requires_mfa=bool_from_request(request.data.get("requires_mfa"), True))
            replace_role_permissions(role, request.data.get("permissions", []))
        except IntegrityError:
            return validation_error("Role code must be unique.", "ROLE_CONFLICT", status.HTTP_409_CONFLICT)
        record_owner_audit(request, "ROLE_CREATED", resource_type="Role", resource_id=str(role.id), after=role_summary(role))
        return JsonResponse({"role": role_summary(role)}, status=status.HTTP_201_CREATED)


class OwnerRoleDetailView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]
    required_permissions = {"GET": "platform.roles.view", "PATCH": "platform.roles.manage"}

    def get(self, request, role_id):
        role = get_object_or_404(Role.objects.prefetch_related("permissions"), id=role_id)
        return JsonResponse({"role": role_summary(role)})

    def patch(self, request, role_id):
        role = get_object_or_404(Role.objects.prefetch_related("permissions"), id=role_id)
        before = role_summary(role)
        if "name" in request.data:
            role.name = str(request.data.get("name", "")).strip()
        if "requires_mfa" in request.data:
            role.requires_mfa = bool_from_request(request.data.get("requires_mfa"), True)
        if "is_active" in request.data:
            role.is_active = bool_from_request(request.data.get("is_active"), True)
        role.save()
        if "permissions" in request.data:
            replace_role_permissions(role, request.data.get("permissions", []))
            audit_action = "PERMISSION_ASSIGNED"
        else:
            audit_action = "ROLE_UPDATED"
        record_owner_audit(request, audit_action, resource_type="Role", resource_id=str(role.id), before=before, after=role_summary(role))
        return JsonResponse({"role": role_summary(role)})


class OwnerRoleActionView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]
    required_permission = "platform.roles.manage"

    def post(self, request, role_id, action):
        role = get_object_or_404(Role.objects.prefetch_related("permissions"), id=role_id)
        before = role_summary(role)
        if action == "disable":
            if role.code == "PLATFORM_ADMIN" and active_platform_admin_count() <= 1:
                return validation_error("The last active Platform Admin role cannot be disabled.", "LAST_PLATFORM_ADMIN_PROTECTED", status.HTTP_409_CONFLICT)
            role.is_active = False
            audit_action = "ROLE_DISABLED"
        elif action == "activate":
            role.is_active = True
            audit_action = "ROLE_UPDATED"
        else:
            return validation_error("Unsupported role action.", "UNKNOWN_ACTION", status.HTTP_404_NOT_FOUND)
        role.save(update_fields=["is_active", "updated_at"])
        record_owner_audit(request, audit_action, resource_type="Role", resource_id=str(role.id), before=before, after=role_summary(role))
        return JsonResponse({"role": role_summary(role)})


class OwnerPermissionListView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]
    required_permission = "platform.permissions.view"

    def get(self, request):
        ensure_default_permissions()
        permissions = Permission.objects.order_by("code")
        return JsonResponse({"permissions": [permission_summary(permission) for permission in permissions]})


class OwnerSupportAccessListCreateView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]
    required_permissions = {"GET": "platform.support_access.view", "POST": "platform.support_access.manage"}

    def get(self, request):
        grants = filter_support_access(request)
        page, paginator, page_size = paginate_queryset(request, grants)
        return JsonResponse({"support_access": [support_access_summary(grant) for grant in page.object_list], "pagination": pagination_summary(page, paginator, page_size)})

    def post(self, request):
        user = get_object_or_404(get_user_model(), id=request.data.get("user_id"))
        tenant = get_object_or_404(Tenant, id=request.data.get("tenant_id"))
        hours = int(request.data.get("hours", 4) or 4)
        if hours < 1 or hours > 24:
            return validation_error("Support access duration must be between 1 and 24 hours.")
        requested = bool_from_request(request.data.get("requested"), False)
        now = timezone.now()
        grant = PlatformTenantAccessGrant.objects.create(
            user=user,
            tenant=tenant,
            approved_by=None if requested else request.user,
            reason=str(request.data.get("reason", "")).strip()[:240] or "Owner approved support access",
            scope=str(request.data.get("scope", "tenant")).strip()[:80] or "tenant",
            starts_at=None if requested else now,
            approved_at=None if requested else now,
            expires_at=now + timezone.timedelta(hours=hours),
            status=PlatformTenantAccessGrant.Status.REQUESTED if requested else PlatformTenantAccessGrant.Status.ACTIVE,
        )
        record_owner_audit(request, "SUPPORT_ACCESS_REQUESTED" if requested else "SUPPORT_ACCESS_APPROVED", resource_type="PlatformTenantAccessGrant", resource_id=str(grant.id), after=support_access_summary(grant))
        return JsonResponse({"support_access": support_access_summary(grant)}, status=status.HTTP_201_CREATED)


class OwnerSupportAccessRevokeView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]
    required_permission = "platform.support_access.manage"

    def post(self, request, grant_id):
        grant = get_object_or_404(PlatformTenantAccessGrant.objects.select_related("user", "tenant", "approved_by"), id=grant_id)
        before = support_access_summary(grant)
        grant.revoked_at = timezone.now()
        grant.save(update_fields=["revoked_at", "updated_at"])
        record_owner_audit(request, "SUPPORT_ACCESS_REVOKED", resource_type="PlatformTenantAccessGrant", resource_id=str(grant.id), before=before, after=support_access_summary(grant))
        return JsonResponse({"support_access": support_access_summary(grant)})


class OwnerSupportAccessDetailView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]
    required_permissions = {"GET": "platform.support_access.view", "PATCH": "platform.support_access.manage"}

    def get(self, request, grant_id):
        grant = get_object_or_404(PlatformTenantAccessGrant.objects.select_related("user", "tenant", "approved_by"), id=grant_id)
        return JsonResponse({"support_access": support_access_summary(grant)})

    def patch(self, request, grant_id):
        grant = get_object_or_404(PlatformTenantAccessGrant.objects.select_related("user", "tenant", "approved_by"), id=grant_id)
        before = support_access_summary(grant)
        if "reason" in request.data:
            grant.reason = str(request.data.get("reason", "")).strip()[:240]
        if "scope" in request.data:
            grant.scope = str(request.data.get("scope", "tenant")).strip()[:80] or "tenant"
        if "hours" in request.data and grant.starts_at:
            hours = int(request.data.get("hours", 4) or 4)
            if hours < 1 or hours > 24:
                return validation_error("Support access duration must be between 1 and 24 hours.")
            grant.expires_at = grant.starts_at + timezone.timedelta(hours=hours)
        grant.save(update_fields=["reason", "scope", "expires_at", "updated_at"])
        record_owner_audit(request, "SUPPORT_ACCESS_UPDATED", resource_type="PlatformTenantAccessGrant", resource_id=str(grant.id), before=before, after=support_access_summary(grant))
        return JsonResponse({"support_access": support_access_summary(grant)})


class OwnerSupportAccessActionView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]
    required_permission = "platform.support_access.manage"

    def post(self, request, grant_id, action):
        grant = get_object_or_404(PlatformTenantAccessGrant.objects.select_related("user", "tenant", "approved_by"), id=grant_id)
        before = support_access_summary(grant)
        if action == "approve":
            if grant.revoked_at or grant.status == PlatformTenantAccessGrant.Status.DENIED:
                return validation_error("Support access request cannot be approved from its current state.", "INVALID_SUPPORT_ACCESS_TRANSITION")
            grant.approved_by = request.user
            grant.approved_at = timezone.now()
            grant.starts_at = timezone.now()
            grant.status = PlatformTenantAccessGrant.Status.ACTIVE
            audit_action = "SUPPORT_ACCESS_APPROVED"
        elif action == "deny":
            if grant.status != PlatformTenantAccessGrant.Status.REQUESTED:
                return validation_error("Only requested support access can be denied.", "INVALID_SUPPORT_ACCESS_TRANSITION")
            grant.denied_at = timezone.now()
            grant.status = PlatformTenantAccessGrant.Status.DENIED
            audit_action = "SUPPORT_ACCESS_DENIED"
        elif action == "revoke":
            grant.revoked_at = timezone.now()
            grant.status = PlatformTenantAccessGrant.Status.REVOKED
            audit_action = "SUPPORT_ACCESS_REVOKED"
        else:
            return validation_error("Unsupported support access action.", "UNKNOWN_ACTION", status.HTTP_404_NOT_FOUND)
        grant.save(update_fields=["approved_by", "approved_at", "starts_at", "denied_at", "status", "revoked_at", "updated_at"])
        record_owner_audit(request, audit_action, resource_type="PlatformTenantAccessGrant", resource_id=str(grant.id), before=before, after=support_access_summary(grant))
        return JsonResponse({"support_access": support_access_summary(grant)})


class OwnerSessionsView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]
    required_permission = "platform.security.view"

    def get(self, request):
        sessions = SecuritySession.objects.select_related("user", "tenant").order_by("-last_seen_at")
        return JsonResponse({"sessions": [session_summary(session) for session in sessions]})


class OwnerSessionRevokeView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]
    required_permission = "platform.security.view"

    def post(self, request, session_id):
        session = get_object_or_404(SecuritySession, id=session_id)
        before = session_summary(session)
        session.revoked_at = timezone.now()
        session.revoke_reason = str(request.data.get("reason", "Owner revoked session")).strip()[:160]
        session.save(update_fields=["revoked_at", "revoke_reason", "updated_at"])
        record_owner_audit(request, "SESSION_REVOKED", resource_type="SecuritySession", resource_id=str(session.id), before=before, after=session_summary(session))
        return JsonResponse({"session": session_summary(session)})


class OwnerMfaComplianceView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]
    required_permission = "platform.security.view"

    def get(self, request):
        users = get_user_model().objects.filter(is_active=True).filter(is_staff=True).order_by("email")
        return JsonResponse({"mfa_compliance": [user_summary(user) | {"compliance_status": "COMPLIANT" if user_summary(user)["mfa_enabled"] or not user.mfa_required else "NON_COMPLIANT"} for user in users]})


def replace_role_permissions(role: Role, permission_codes) -> None:
    RolePermission.objects.filter(role=role).delete()
    for code in permission_codes or []:
        permission, _ = Permission.objects.get_or_create(code=str(code).strip())
        RolePermission.objects.get_or_create(role=role, permission=permission)


def replace_platform_roles(user, role_codes) -> None:
    normalized = [str(code).strip().upper() for code in role_codes or [] if str(code).strip()]
    if not normalized:
        PlatformUserRole.objects.filter(user=user).delete()
        return
    roles = Role.objects.filter(code__in=normalized, scope=Role.Scope.PLATFORM, is_active=True)
    PlatformUserRole.objects.filter(user=user).exclude(role__code__in=normalized).delete()
    for role in roles:
        PlatformUserRole.objects.get_or_create(user=user, role=role)
        if role.code == "PLATFORM_ADMIN":
            user.is_staff = True
            user.is_platform_admin = True
            user.mfa_required = True
            user.save(update_fields=["is_staff", "is_platform_admin", "mfa_required", "updated_at"])


def ensure_default_roles() -> None:
    ensure_default_permissions()
    defaults = [
        ("PLATFORM_ADMIN", "Platform Admin", True, list(DEFAULT_PLATFORM_PERMISSIONS)),
        ("PLATFORM_SECURITY_ADMIN", "Platform Security Admin", True, ["platform.security.view", "platform.audit.view", "platform.users.manage"]),
        ("PLATFORM_SUPPORT", "Platform Support", False, ["platform.tenants.view", "platform.support_access.manage"]),
    ]
    for code, name, requires_mfa, permissions in defaults:
        role, _created = Role.objects.get_or_create(code=code, defaults={"name": name, "scope": Role.Scope.PLATFORM, "requires_mfa": requires_mfa, "is_active": True})
        replace_role_permissions(role, permissions)


def ensure_default_permissions() -> None:
    for code in DEFAULT_PLATFORM_PERMISSIONS:
        Permission.objects.get_or_create(code=code)


DEFAULT_PLATFORM_PERMISSIONS = [
    "platform.dashboard.view",
    "platform.tenants.view",
    "platform.tenants.create",
    "platform.tenants.edit",
    "platform.tenants.suspend",
    "platform.tenants.provision",
    "platform.domains.view",
    "platform.domains.manage",
    "platform.plans.view",
    "platform.plans.manage",
    "platform.subscriptions.view",
    "platform.subscriptions.manage",
    "platform.modules.view",
    "platform.modules.manage",
    "platform.features.view",
    "platform.features.manage",
    "platform.licenses.view",
    "platform.licenses.manage",
    "platform.users.view",
    "platform.users.manage",
    "platform.roles.view",
    "platform.roles.manage",
    "platform.permissions.view",
    "platform.support_access.view",
    "platform.support_access.manage",
    "platform.infrastructure.view",
    "platform.infrastructure.manage",
    "platform.security.view",
    "platform.audit.view",
    "platform.reports.view",
    "platform.reports.export",
    "platform.settings.view",
    "platform.settings.manage",
    "platform.notifications.view",
    "platform.notifications.manage",
]


def active_platform_admin_count() -> int:
    return get_user_model().objects.filter(is_active=True, is_platform_admin=True).count()


def would_disable_last_platform_admin(user) -> bool:
    return bool(user.is_active and user.is_platform_admin and active_platform_admin_count() <= 1)


def filter_platform_users(request):
    users = get_user_model().objects.order_by("email")
    search = request.GET.get("search", "").strip()
    if search:
        users = users.filter(Q(email__icontains=search) | Q(first_name__icontains=search) | Q(last_name__icontains=search))
    if request.GET.get("active"):
        users = users.filter(is_active=bool_from_request(request.GET.get("active")))
    return users


def filter_roles(request):
    roles = Role.objects.prefetch_related("permissions").order_by("scope", "code")
    search = request.GET.get("search", "").strip()
    if search:
        roles = roles.filter(Q(code__icontains=search) | Q(name__icontains=search))
    if request.GET.get("active"):
        roles = roles.filter(is_active=bool_from_request(request.GET.get("active")))
    if request.GET.get("scope"):
        roles = roles.filter(scope=request.GET.get("scope"))
    return roles


def filter_support_access(request):
    grants = PlatformTenantAccessGrant.objects.select_related("user", "tenant", "approved_by").order_by("-created_at")
    search = request.GET.get("search", "").strip()
    if search:
        grants = grants.filter(Q(user__email__icontains=search) | Q(tenant__tenant_code__icontains=search) | Q(tenant__display_name__icontains=search) | Q(reason__icontains=search))
    if request.GET.get("status"):
        grants = grants.filter(status=request.GET.get("status"))
    return grants


def paginate_queryset(request, queryset):
    page_size = min(max(int(request.GET.get("page_size", 25) or 25), 1), 100)
    paginator = Paginator(queryset, page_size)
    page_number = max(int(request.GET.get("page", 1) or 1), 1)
    return paginator.get_page(page_number), paginator, page_size


def pagination_summary(page, paginator, page_size: int) -> dict:
    return {"page": page.number, "page_size": page_size, "total": paginator.count, "pages": paginator.num_pages, "has_next": page.has_next(), "has_previous": page.has_previous()}
