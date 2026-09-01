from __future__ import annotations

import json
from typing import Any

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from audit.models import AuditEvent
from control.models import Tenant, TenantMembership
from identity.models import WarehouseAssignment
from tenancy.context import get_tenant_context
from warehouse.models import Bin, LifecycleStatus, Plant, StorageSection, StorageType, Warehouse, Zone


class TenantAdminPermission(IsAuthenticated):
    def has_permission(self, request, view) -> bool:
        if not super().has_permission(request, view):
            return False
        context = get_tenant_context()
        return TenantMembership.objects.filter(
            user=request.user,
            tenant_id=context.tenant_id,
            status=TenantMembership.Status.ACTIVE,
        ).exists()


class TenantDashboardView(APIView):
    permission_classes = [TenantAdminPermission]
    throttle_scope = "standard_api"

    def get(self, request):
        context = get_tenant_context()
        membership = _membership(request)
        return JsonResponse(
            {
                "tenant": {"id": str(context.tenant_id), "code": context.tenant_code},
                "summary": {
                    "plants": Plant.objects.count(),
                    "warehouses": Warehouse.objects.count(),
                    "zones": Zone.objects.count(),
                    "storage_types": StorageType.objects.count(),
                    "sections": StorageSection.objects.count(),
                    "bins": Bin.objects.count(),
                    "active_users": TenantMembership.objects.filter(tenant_id=context.tenant_id, status=TenantMembership.Status.ACTIVE).count(),
                    "assigned_warehouses": membership.warehouse_assignments.filter(is_active=True).count() if membership else 0,
                },
            }
        )


class ActiveWarehouseContextView(APIView):
    permission_classes = [TenantAdminPermission]
    throttle_scope = "standard_api"

    def post(self, request):
        warehouse_id = request.data.get("warehouse_id")
        warehouse = get_object_or_404(Warehouse, id=warehouse_id, status=LifecycleStatus.ACTIVE, is_active=True)
        membership = _membership(request)
        if membership is None or not WarehouseAssignment.objects.filter(
            membership=membership,
            warehouse_code=warehouse.code,
            is_active=True,
        ).exists():
            return _error("WAREHOUSE_ACCESS_DENIED", "Warehouse access denied.", 403)
        request.session["active_warehouse_id"] = str(warehouse.id)
        _audit(request, "WAREHOUSE_ASSIGNMENT_CHANGE", "warehouse", str(warehouse.id), after={"active_warehouse": warehouse.code})
        return JsonResponse({"active_warehouse": serialize_warehouse(warehouse)})


class HierarchyListCreateView(APIView):
    permission_classes = [TenantAdminPermission]
    throttle_scope = "standard_api"

    model = Plant
    serializer = staticmethod(lambda item: {})
    create_fields: tuple[str, ...] = ()
    action_create = ""

    def get(self, request):
        rows = self.model.objects.all().order_by("created_at")
        search = str(request.GET.get("search", "")).strip()
        status = str(request.GET.get("status", "")).strip()
        if status:
            rows = rows.filter(status=status)
        if search:
            rows = self._search(rows, search)
        page = max(int(request.GET.get("page", "1")), 1)
        page_size = min(max(int(request.GET.get("page_size", "25")), 1), 100)
        total = rows.count()
        start = (page - 1) * page_size
        return JsonResponse(
            {
                "count": total,
                "page": page,
                "page_size": page_size,
                "results": [self.serializer(item) for item in rows[start : start + page_size]],
            }
        )

    def post(self, request):
        return self._save(request, self.model(), self.action_create)

    def _save(self, request, instance, action: str):
        for field in self.create_fields:
            if field in request.data:
                setattr(instance, field, request.data[field])
        if hasattr(instance, "is_active"):
            instance.is_active = getattr(instance, "status", LifecycleStatus.ACTIVE) == LifecycleStatus.ACTIVE
        try:
            with transaction.atomic(using=get_tenant_context().database_alias):
                instance.full_clean()
                instance.save()
        except ValidationError as exc:
            return _error("VALIDATION_ERROR", exc.message_dict if hasattr(exc, "message_dict") else exc.messages, 400)
        except IntegrityError:
            return _error("DUPLICATE_CODE", "Duplicate code or barcode.", 400)
        _audit(request, action, instance._meta.model_name, str(instance.pk), after=self.serializer(instance))
        return JsonResponse(self.serializer(instance), status=201)

    def _search(self, rows, search: str):
        return rows


class HierarchyDetailView(HierarchyListCreateView):
    action_update = ""
    action_status = ""

    def get(self, request, item_id):
        return JsonResponse(self.serializer(get_object_or_404(self.model, id=item_id)))

    def patch(self, request, item_id):
        instance = get_object_or_404(self.model, id=item_id)
        before = self.serializer(instance)
        response = self._save(request, instance, self.action_update)
        if response.status_code == 201:
            response.status_code = 200
            if "status" in request.data:
                _audit(request, self.action_status, instance._meta.model_name, str(instance.pk), before=before, after=self.serializer(instance))
        return response


class PlantListCreateView(HierarchyListCreateView):
    model = Plant
    serializer = staticmethod(lambda item: serialize_plant(item))
    create_fields = (
        "plant_code",
        "name",
        "description",
        "status",
        "address_line_1",
        "address_line_2",
        "city",
        "state",
        "postal_code",
        "country",
        "timezone",
        "latitude",
        "longitude",
        "contact_name",
        "contact_phone",
        "contact_email",
    )
    action_create = "PLANT_CREATE"

    def _search(self, rows, search: str):
        return rows.filter(plant_code__icontains=search) | rows.filter(name__icontains=search)


class PlantDetailView(HierarchyDetailView):
    model = Plant
    serializer = staticmethod(lambda item: serialize_plant(item))
    create_fields = PlantListCreateView.create_fields
    action_update = "PLANT_UPDATE"
    action_status = "PLANT_STATUS_CHANGE"


class WarehouseListCreateView(HierarchyListCreateView):
    model = Warehouse
    serializer = staticmethod(lambda item: serialize_warehouse(item))
    create_fields = (
        "code",
        "name",
        "plant_id",
        "description",
        "status",
        "warehouse_type",
        "timezone",
        "address_line_1",
        "address_line_2",
        "city",
        "state",
        "postal_code",
        "country",
        "capacity_metadata",
    )
    action_create = "WAREHOUSE_CREATE"

    def _search(self, rows, search: str):
        return rows.filter(code__icontains=search) | rows.filter(name__icontains=search)


class WarehouseDetailView(HierarchyDetailView):
    model = Warehouse
    serializer = staticmethod(lambda item: serialize_warehouse(item))
    create_fields = WarehouseListCreateView.create_fields
    action_update = "WAREHOUSE_UPDATE"
    action_status = "WAREHOUSE_STATUS_CHANGE"


class ZoneListCreateView(HierarchyListCreateView):
    model = Zone
    serializer = staticmethod(lambda item: serialize_zone(item))
    create_fields = ("warehouse_id", "zone_code", "name", "zone_type", "status", "description", "sequence")
    action_create = "ZONE_CREATE"

    def _search(self, rows, search: str):
        return rows.filter(zone_code__icontains=search) | rows.filter(name__icontains=search)


class ZoneDetailView(HierarchyDetailView):
    model = Zone
    serializer = staticmethod(lambda item: serialize_zone(item))
    create_fields = ZoneListCreateView.create_fields
    action_update = "ZONE_UPDATE"
    action_status = "ZONE_STATUS_CHANGE"


class StorageTypeListCreateView(HierarchyListCreateView):
    model = StorageType
    serializer = staticmethod(lambda item: serialize_storage_type(item))
    create_fields = ("warehouse_id", "storage_type_code", "name", "description", "status", "capacity_rules", "handling_rules")
    action_create = "STORAGE_TYPE_CREATE"

    def _search(self, rows, search: str):
        return rows.filter(storage_type_code__icontains=search) | rows.filter(name__icontains=search)


class StorageTypeDetailView(HierarchyDetailView):
    model = StorageType
    serializer = staticmethod(lambda item: serialize_storage_type(item))
    create_fields = StorageTypeListCreateView.create_fields
    action_update = "STORAGE_TYPE_UPDATE"


class StorageSectionListCreateView(HierarchyListCreateView):
    model = StorageSection
    serializer = staticmethod(lambda item: serialize_section(item))
    create_fields = ("warehouse_id", "zone_id", "storage_type_id", "section_code", "name", "status", "sequence", "description")
    action_create = "SECTION_CREATE"

    def _search(self, rows, search: str):
        return rows.filter(section_code__icontains=search) | rows.filter(name__icontains=search)


class StorageSectionDetailView(HierarchyDetailView):
    model = StorageSection
    serializer = staticmethod(lambda item: serialize_section(item))
    create_fields = StorageSectionListCreateView.create_fields
    action_update = "SECTION_UPDATE"


class BinListCreateView(HierarchyListCreateView):
    model = Bin
    serializer = staticmethod(lambda item: serialize_bin(item))
    create_fields = (
        "warehouse_id",
        "zone_id",
        "storage_type_id",
        "section_id",
        "bin_code",
        "barcode",
        "status",
        "aisle",
        "bay",
        "level",
        "position",
        "max_weight",
        "max_volume",
        "max_hu_count",
        "is_pickable",
        "is_putaway_allowed",
        "is_blocked",
        "is_countable",
    )
    action_create = "BIN_CREATE"

    def _search(self, rows, search: str):
        return rows.filter(bin_code__icontains=search) | rows.filter(barcode__icontains=search)


class BinDetailView(HierarchyDetailView):
    model = Bin
    serializer = staticmethod(lambda item: serialize_bin(item))
    create_fields = BinListCreateView.create_fields
    action_update = "BIN_UPDATE"
    action_status = "BIN_BLOCK"


def serialize_plant(plant: Plant) -> dict[str, Any]:
    return {
        "id": str(plant.id),
        "plant_code": plant.plant_code,
        "name": plant.name,
        "description": plant.description,
        "status": plant.status,
        "city": plant.city,
        "state": plant.state,
        "country": plant.country,
        "timezone": plant.timezone,
        "created_at": plant.created_at.isoformat(),
        "updated_at": plant.updated_at.isoformat(),
    }


def serialize_warehouse(warehouse: Warehouse) -> dict[str, Any]:
    return {
        "id": str(warehouse.id),
        "warehouse_code": warehouse.code,
        "name": warehouse.name,
        "plant_id": str(warehouse.plant_id) if warehouse.plant_id else None,
        "status": warehouse.status,
        "is_active": warehouse.is_active,
        "warehouse_type": warehouse.warehouse_type,
        "timezone": warehouse.timezone,
        "created_at": warehouse.created_at.isoformat(),
        "updated_at": warehouse.updated_at.isoformat(),
    }


def serialize_zone(zone: Zone) -> dict[str, Any]:
    return {
        "id": str(zone.id),
        "warehouse_id": str(zone.warehouse_id),
        "zone_code": zone.zone_code,
        "name": zone.name,
        "zone_type": zone.zone_type,
        "status": zone.status,
        "sequence": zone.sequence,
    }


def serialize_storage_type(storage_type: StorageType) -> dict[str, Any]:
    return {
        "id": str(storage_type.id),
        "warehouse_id": str(storage_type.warehouse_id),
        "storage_type_code": storage_type.storage_type_code,
        "name": storage_type.name,
        "status": storage_type.status,
    }


def serialize_section(section: StorageSection) -> dict[str, Any]:
    return {
        "id": str(section.id),
        "warehouse_id": str(section.warehouse_id),
        "zone_id": str(section.zone_id),
        "storage_type_id": str(section.storage_type_id),
        "section_code": section.section_code,
        "name": section.name,
        "status": section.status,
        "sequence": section.sequence,
    }


def serialize_bin(bin_: Bin) -> dict[str, Any]:
    return {
        "id": str(bin_.id),
        "warehouse_id": str(bin_.warehouse_id),
        "zone_id": str(bin_.zone_id),
        "storage_type_id": str(bin_.storage_type_id),
        "section_id": str(bin_.section_id) if bin_.section_id else None,
        "bin_code": bin_.bin_code,
        "barcode": bin_.barcode,
        "status": bin_.status,
        "aisle": bin_.aisle,
        "bay": bin_.bay,
        "level": bin_.level,
        "position": bin_.position,
        "is_pickable": bin_.is_pickable,
        "is_putaway_allowed": bin_.is_putaway_allowed,
        "is_blocked": bin_.is_blocked,
        "is_countable": bin_.is_countable,
    }


def _membership(request):
    context = get_tenant_context()
    return TenantMembership.objects.filter(user=request.user, tenant_id=context.tenant_id, status=TenantMembership.Status.ACTIVE).first()


def _audit(request, action: str, resource_type: str, resource_id: str, *, before=None, after=None):
    context = get_tenant_context()
    AuditEvent.objects.create(
        request_id=getattr(request, "request_id", ""),
        tenant_id=context.tenant_id,
        global_user_id=request.user.id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        before_summary=_safe_json(before or {}),
        after_summary=_safe_json(after or {}),
        result=AuditEvent.Result.SUCCESS,
    )


def _safe_json(value):
    return json.loads(json.dumps(value, default=str))


def _error(code: str, message, status_code: int) -> JsonResponse:
    return JsonResponse({"error": {"code": code, "message": message}}, status=status_code)
