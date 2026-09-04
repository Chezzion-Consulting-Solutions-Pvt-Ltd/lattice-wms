from __future__ import annotations

from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView

from control.api.common import IsOwnerConsoleUser, bool_from_request, record_owner_audit, validation_error
from control.api.serializers import domain_summary
from control.models import Tenant, TenantDomain


class OwnerTenantDomainListCreateView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]
    required_permissions = {"GET": "platform.domains.view", "POST": "platform.domains.manage"}

    def get(self, request, tenant_id):
        tenant = get_object_or_404(Tenant, id=tenant_id)
        domains = tenant.domains.order_by("-is_primary", "hostname")
        return JsonResponse({"domains": [domain_summary(domain) for domain in domains]})

    def post(self, request, tenant_id):
        tenant = get_object_or_404(Tenant, id=tenant_id)
        hostname = normalize_hostname(str(request.data.get("hostname", "")))
        if not hostname:
            return validation_error("Domain hostname is required.")
        method = str(request.data.get("verification_method", TenantDomain.VerificationMethod.DNS_TXT))
        if method not in TenantDomain.VerificationMethod.values:
            return validation_error("Unsupported domain verification method.")
        try:
            domain = TenantDomain.objects.create(
                tenant=tenant,
                hostname=hostname,
                verification_method=method,
                is_primary=bool_from_request(request.data.get("is_primary"), False),
                is_active=False,
                verified=False,
            )
        except IntegrityError:
            return validation_error("Domain hostname is already registered.", "DOMAIN_CONFLICT", status.HTTP_409_CONFLICT)
        if domain.is_primary:
            TenantDomain.objects.filter(tenant=tenant).exclude(id=domain.id).update(is_primary=False)
        record_owner_audit(request, "TENANT_DOMAIN_CREATED", resource_type="TenantDomain", resource_id=str(domain.id), after=domain_summary(domain))
        return JsonResponse({"domain": domain_summary(domain)}, status=status.HTTP_201_CREATED)


class OwnerTenantDomainActionView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]
    required_permission = "platform.domains.manage"

    def post(self, request, tenant_id, domain_id, action):
        domain = get_object_or_404(TenantDomain.objects.select_related("tenant"), id=domain_id, tenant_id=tenant_id)
        before = domain_summary(domain)
        if action == "verify-development":
            if domain.verification_method != TenantDomain.VerificationMethod.LOCAL_DEVELOPMENT:
                return validation_error("Only local development domains can be verified through this action.")
            domain.verified = True
            domain.verified_at = timezone.now()
            audit_action = "TENANT_DOMAIN_VERIFIED"
        elif action == "activate":
            if not domain.verified:
                return validation_error("Only verified domains can be activated.", "DOMAIN_NOT_VERIFIED", status.HTTP_409_CONFLICT)
            domain.is_active = True
            audit_action = "TENANT_DOMAIN_ACTIVATED"
        elif action == "deactivate":
            domain.is_active = False
            audit_action = "TENANT_DOMAIN_DEACTIVATED"
        elif action == "make-primary":
            if not domain.verified or not domain.is_active:
                return validation_error("Only active verified domains can be made primary.", "DOMAIN_NOT_READY", status.HTTP_409_CONFLICT)
            with transaction.atomic():
                TenantDomain.objects.filter(tenant=domain.tenant).exclude(id=domain.id).update(is_primary=False)
                domain.is_primary = True
                domain.save(update_fields=["is_primary", "updated_at"])
            record_owner_audit(request, "TENANT_DOMAIN_PRIMARY_CHANGED", resource_type="TenantDomain", resource_id=str(domain.id), before=before, after=domain_summary(domain))
            return JsonResponse({"domain": domain_summary(domain)})
        else:
            return validation_error("Unsupported domain action.", "UNKNOWN_ACTION", status.HTTP_404_NOT_FOUND)
        domain.save(update_fields=["verified", "verified_at", "is_active", "updated_at"])
        record_owner_audit(request, audit_action, resource_type="TenantDomain", resource_id=str(domain.id), before=before, after=domain_summary(domain))
        return JsonResponse({"domain": domain_summary(domain)})

    def delete(self, request, tenant_id, domain_id, action=None):
        domain = get_object_or_404(TenantDomain.objects.select_related("tenant"), id=domain_id, tenant_id=tenant_id)
        if domain.verified and domain.is_active:
            return validation_error("Active verified domains must be deactivated before removal.", "DOMAIN_ACTIVE", status.HTTP_409_CONFLICT)
        before = domain_summary(domain)
        domain_id_text = str(domain.id)
        domain.delete()
        record_owner_audit(request, "TENANT_DOMAIN_REMOVED", resource_type="TenantDomain", resource_id=domain_id_text, before=before)
        return JsonResponse({"removed": True})


def normalize_hostname(hostname: str) -> str:
    return hostname.split(":", 1)[0].strip().lower().rstrip(".")
