from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView

from control.api.common import IsOwnerConsoleUser, bool_from_request, record_owner_audit, validation_error
from control.api.serializers import permission_summary, role_summary, session_summary, support_access_summary, user_summary
from control.models import Tenant
from identity.models import Permission, PlatformTenantAccessGrant, Role, RolePermission, SecuritySession


class OwnerPlatformUserListCreateView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]

    def get(self, request):
        users = get_user_model().objects.order_by("email")
        return JsonResponse({"users": [user_summary(user) for user in users]})

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
        except IntegrityError:
            return validation_error("A platform user with this email already exists.", "USER_CONFLICT", status.HTTP_409_CONFLICT)
        record_owner_audit(request, "PLATFORM_USER_CREATED", resource_type="GlobalUser", resource_id=str(user.id), after=user_summary(user))
        return JsonResponse({"user": user_summary(user)}, status=status.HTTP_201_CREATED)


class OwnerPlatformUserDetailView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]

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
        record_owner_audit(request, "PLATFORM_USER_UPDATED" if user.is_active else "PLATFORM_USER_DISABLED", resource_type="GlobalUser", resource_id=str(user.id), before=before, after=user_summary(user))
        return JsonResponse({"user": user_summary(user)})


class OwnerRoleListCreateView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]

    def get(self, request):
        roles = Role.objects.prefetch_related("permissions").order_by("scope", "code")
        return JsonResponse({"roles": [role_summary(role) for role in roles]})

    def post(self, request):
        code = str(request.data.get("code", "")).strip().upper()
        name = str(request.data.get("name", "")).strip()
        if not code or not name:
            return validation_error("Role code and name are required.")
        try:
            role = Role.objects.create(code=code, name=name, scope=str(request.data.get("scope", Role.Scope.PLATFORM)), requires_mfa=bool_from_request(request.data.get("requires_mfa"), True))
            replace_role_permissions(role, request.data.get("permissions", []))
        except IntegrityError:
            return validation_error("Role code must be unique.", "ROLE_CONFLICT", status.HTTP_409_CONFLICT)
        record_owner_audit(request, "ROLE_CREATED", resource_type="Role", resource_id=str(role.id), after=role_summary(role))
        return JsonResponse({"role": role_summary(role)}, status=status.HTTP_201_CREATED)


class OwnerRoleDetailView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]

    def patch(self, request, role_id):
        role = get_object_or_404(Role.objects.prefetch_related("permissions"), id=role_id)
        before = role_summary(role)
        if "name" in request.data:
            role.name = str(request.data.get("name", "")).strip()
        if "requires_mfa" in request.data:
            role.requires_mfa = bool_from_request(request.data.get("requires_mfa"), True)
        role.save()
        if "permissions" in request.data:
            replace_role_permissions(role, request.data.get("permissions", []))
            audit_action = "PERMISSION_ASSIGNED"
        else:
            audit_action = "ROLE_UPDATED"
        record_owner_audit(request, audit_action, resource_type="Role", resource_id=str(role.id), before=before, after=role_summary(role))
        return JsonResponse({"role": role_summary(role)})


class OwnerPermissionListView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]

    def get(self, request):
        ensure_default_permissions()
        permissions = Permission.objects.order_by("code")
        return JsonResponse({"permissions": [permission_summary(permission) for permission in permissions]})


class OwnerSupportAccessListCreateView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]

    def get(self, request):
        grants = PlatformTenantAccessGrant.objects.select_related("user", "tenant", "approved_by").order_by("-created_at")
        return JsonResponse({"support_access": [support_access_summary(grant) for grant in grants]})

    def post(self, request):
        user = get_object_or_404(get_user_model(), id=request.data.get("user_id"))
        tenant = get_object_or_404(Tenant, id=request.data.get("tenant_id"))
        hours = int(request.data.get("hours", 4) or 4)
        if hours < 1 or hours > 24:
            return validation_error("Support access duration must be between 1 and 24 hours.")
        grant = PlatformTenantAccessGrant.objects.create(
            user=user,
            tenant=tenant,
            approved_by=request.user,
            reason=str(request.data.get("reason", "")).strip()[:240] or "Owner approved support access",
            expires_at=timezone.now() + timezone.timedelta(hours=hours),
        )
        record_owner_audit(request, "SUPPORT_ACCESS_APPROVED", resource_type="PlatformTenantAccessGrant", resource_id=str(grant.id), after=support_access_summary(grant))
        return JsonResponse({"support_access": support_access_summary(grant)}, status=status.HTTP_201_CREATED)


class OwnerSupportAccessRevokeView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]

    def post(self, request, grant_id):
        grant = get_object_or_404(PlatformTenantAccessGrant.objects.select_related("user", "tenant", "approved_by"), id=grant_id)
        before = support_access_summary(grant)
        grant.revoked_at = timezone.now()
        grant.save(update_fields=["revoked_at", "updated_at"])
        record_owner_audit(request, "SUPPORT_ACCESS_REVOKED", resource_type="PlatformTenantAccessGrant", resource_id=str(grant.id), before=before, after=support_access_summary(grant))
        return JsonResponse({"support_access": support_access_summary(grant)})


class OwnerSessionsView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]

    def get(self, request):
        sessions = SecuritySession.objects.select_related("user", "tenant").order_by("-last_seen_at")
        return JsonResponse({"sessions": [session_summary(session) for session in sessions]})


class OwnerSessionRevokeView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]

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

    def get(self, request):
        users = get_user_model().objects.filter(is_active=True).filter(is_staff=True).order_by("email")
        return JsonResponse({"mfa_compliance": [user_summary(user) | {"compliance_status": "COMPLIANT" if user_summary(user)["mfa_enabled"] or not user.mfa_required else "NON_COMPLIANT"} for user in users]})


def replace_role_permissions(role: Role, permission_codes) -> None:
    RolePermission.objects.filter(role=role).delete()
    for code in permission_codes or []:
        permission, _ = Permission.objects.get_or_create(code=str(code).strip())
        RolePermission.objects.get_or_create(role=role, permission=permission)


def ensure_default_permissions() -> None:
    for code in [
        "platform.tenants.view",
        "platform.tenants.create",
        "platform.tenants.edit",
        "platform.tenants.suspend",
        "platform.plans.view",
        "platform.plans.manage",
        "platform.subscriptions.view",
        "platform.subscriptions.manage",
        "platform.modules.view",
        "platform.modules.manage",
        "platform.users.view",
        "platform.users.manage",
        "platform.roles.view",
        "platform.roles.manage",
        "platform.infrastructure.view",
        "platform.infrastructure.manage",
        "platform.security.view",
        "platform.audit.view",
        "platform.reports.view",
        "platform.reports.export",
        "platform.settings.view",
        "platform.settings.manage",
    ]:
        Permission.objects.get_or_create(code=code)
