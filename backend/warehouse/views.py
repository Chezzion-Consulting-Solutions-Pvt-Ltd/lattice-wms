from __future__ import annotations

import json
from typing import Any

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from audit.models import AuditEvent
from control.models import Tenant, TenantMembership
from identity.authorization import has_permission
from identity.models import WarehouseAssignment
from tenancy.context import get_tenant_context
from warehouse.models import Bin, LifecycleStatus, Plant, ProductCategory, StorageSection, StorageType, Warehouse, Zone


class TenantAdminPermission(IsAuthenticated):
    def has_permission(self, request, view) -> bool:
        if not super().has_permission(request, view):
            return False
        context = get_tenant_context()
        membership_exists = TenantMembership.objects.filter(
            user=request.user,
            tenant_id=context.tenant_id,
            status=TenantMembership.Status.ACTIVE,
        ).exists()
        if not membership_exists:
            return False
        required_permission = getattr(view, "required_write_permission", "") if request.method in {"POST", "PATCH", "PUT", "DELETE"} else getattr(view, "required_read_permission", "")
        if required_permission:
            tenant = Tenant.objects.get(id=context.tenant_id)
            return has_permission(request.user, tenant, required_permission)
        return True


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
                "setup": {
                    "hierarchy_ready": Warehouse.objects.filter(status=LifecycleStatus.ACTIVE, is_active=True).exists(),
                    "active_warehouse_id": request.session.get("active_warehouse_id"),
                    "active_warehouse_code": request.session.get("active_warehouse_code"),
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
        request.session["active_warehouse_code"] = warehouse.code
        _audit(request, "ACTIVE_WAREHOUSE_CHANGED", "warehouse", str(warehouse.id), after={"active_warehouse": warehouse.code})
        return JsonResponse({"active_warehouse": serialize_warehouse(warehouse)})


class HierarchyListCreateView(APIView):
    permission_classes = [TenantAdminPermission]
    throttle_scope = "standard_api"

    model = Plant
    serializer = staticmethod(lambda item: {})
    create_fields: tuple[str, ...] = ()
    action_create = ""
    required_read_permission = ""
    required_write_permission = ""

    def get(self, request):
        rows = self.model.objects.all().order_by("created_at")
        search = str(request.GET.get("search", "")).strip()
        status = str(request.GET.get("status", "")).strip()
        if status:
            rows = rows.filter(status=status)
        rows = self._filter(request, rows)
        if search:
            rows = self._search(request, rows, search)
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
        if instance.pk and hasattr(instance, "updated_by_user_id"):
            instance.updated_by_user_id = request.user.id
        elif hasattr(instance, "created_by_user_id"):
            instance.created_by_user_id = request.user.id
            instance.updated_by_user_id = request.user.id
        if hasattr(instance, "is_active"):
            instance.is_active = getattr(instance, "status", LifecycleStatus.ACTIVE) == LifecycleStatus.ACTIVE
        try:
            with transaction.atomic(using=get_tenant_context().database_alias):
                instance.full_clean()
                instance.save()
        except ValidationError as exc:
            if _is_duplicate_validation(exc):
                return _error("DUPLICATE_CODE", "Duplicate code or barcode.", 400)
            return _error("VALIDATION_ERROR", exc.message_dict if hasattr(exc, "message_dict") else exc.messages, 400)
        except IntegrityError:
            return _error("DUPLICATE_CODE", "Duplicate code or barcode.", 400)
        _audit(request, action, instance._meta.model_name, str(instance.pk), after=self.serializer(instance))
        return JsonResponse(self.serializer(instance), status=201)

    def _search(self, request, rows, search: str):
        return rows

    def _filter(self, request, rows):
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
    action_create = "PLANT_CREATED"
    required_read_permission = "organization.plants.view"
    required_write_permission = "organization.plants.manage"

    def _search(self, request, rows, search: str):
        return rows.filter(Q(plant_code__icontains=search) | Q(name__icontains=search))


class PlantDetailView(HierarchyDetailView):
    model = Plant
    serializer = staticmethod(lambda item: serialize_plant(item))
    create_fields = PlantListCreateView.create_fields
    action_update = "PLANT_UPDATED"
    action_status = "PLANT_STATUS_CHANGED"


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
    action_create = "WAREHOUSE_CREATED"
    required_read_permission = "organization.warehouses.view"
    required_write_permission = "organization.warehouses.manage"

    def _search(self, request, rows, search: str):
        return rows.filter(Q(code__icontains=search) | Q(name__icontains=search))


class WarehouseDetailView(HierarchyDetailView):
    model = Warehouse
    serializer = staticmethod(lambda item: serialize_warehouse(item))
    create_fields = WarehouseListCreateView.create_fields
    action_update = "WAREHOUSE_UPDATED"
    action_status = "WAREHOUSE_STATUS_CHANGED"


class ProductCategoryListCreateView(HierarchyListCreateView):
    model = ProductCategory
    serializer = staticmethod(lambda item: serialize_product_category(item))
    create_fields = ("category_code", "name", "description", "parent_category_id", "status")
    action_create = "PRODUCT_CATEGORY_CREATED"
    required_read_permission = "masters.categories.view"
    required_write_permission = "masters.categories.manage"

    def _search(self, request, rows, search: str):
        return rows.filter(Q(category_code__icontains=search) | Q(name__icontains=search))


class ProductCategoryDetailView(HierarchyDetailView):
    model = ProductCategory
    serializer = staticmethod(lambda item: serialize_product_category(item))
    create_fields = ProductCategoryListCreateView.create_fields
    action_update = "PRODUCT_CATEGORY_UPDATED"
    action_status = "PRODUCT_CATEGORY_STATUS_CHANGED"


class ZoneListCreateView(HierarchyListCreateView):
    model = Zone
    serializer = staticmethod(lambda item: serialize_zone(item))
    create_fields = ("warehouse_id", "zone_code", "name", "zone_type", "status", "description", "sequence")
    action_create = "ZONE_CREATED"
    required_read_permission = "organization.zones.view"
    required_write_permission = "organization.zones.manage"

    def _filter(self, request, rows):
        warehouse_id = request.GET.get("warehouse_id")
        zone_type = request.GET.get("zone_type")
        if warehouse_id:
            rows = rows.filter(warehouse_id=warehouse_id)
        if zone_type:
            rows = rows.filter(zone_type=zone_type)
        return rows

    def _search(self, request, rows, search: str):
        return rows.filter(Q(zone_code__icontains=search) | Q(name__icontains=search))


class ZoneDetailView(HierarchyDetailView):
    model = Zone
    serializer = staticmethod(lambda item: serialize_zone(item))
    create_fields = ZoneListCreateView.create_fields
    action_update = "ZONE_UPDATED"
    action_status = "ZONE_STATUS_CHANGED"


class StorageTypeListCreateView(HierarchyListCreateView):
    model = StorageType
    serializer = staticmethod(lambda item: serialize_storage_type(item))
    create_fields = ("warehouse_id", "storage_type_code", "name", "description", "status", "capacity_rules", "handling_rules")
    action_create = "STORAGE_TYPE_CREATED"
    required_read_permission = "organization.storage_types.view"
    required_write_permission = "organization.storage_types.manage"

    def _filter(self, request, rows):
        warehouse_id = request.GET.get("warehouse_id")
        if warehouse_id:
            rows = rows.filter(warehouse_id=warehouse_id)
        return rows

    def _search(self, request, rows, search: str):
        return rows.filter(Q(storage_type_code__icontains=search) | Q(name__icontains=search))


class StorageTypeDetailView(HierarchyDetailView):
    model = StorageType
    serializer = staticmethod(lambda item: serialize_storage_type(item))
    create_fields = StorageTypeListCreateView.create_fields
    action_update = "STORAGE_TYPE_UPDATED"


class StorageSectionListCreateView(HierarchyListCreateView):
    model = StorageSection
    serializer = staticmethod(lambda item: serialize_section(item))
    create_fields = ("warehouse_id", "zone_id", "storage_type_id", "section_code", "name", "status", "sequence", "description")
    action_create = "SECTION_CREATED"
    required_read_permission = "organization.sections.view"
    required_write_permission = "organization.sections.manage"

    def _filter(self, request, rows):
        warehouse_id = request.GET.get("warehouse_id")
        if warehouse_id:
            rows = rows.filter(warehouse_id=warehouse_id)
        return rows

    def _search(self, request, rows, search: str):
        return rows.filter(Q(section_code__icontains=search) | Q(name__icontains=search))


class StorageSectionDetailView(HierarchyDetailView):
    model = StorageSection
    serializer = staticmethod(lambda item: serialize_section(item))
    create_fields = StorageSectionListCreateView.create_fields
    action_update = "SECTION_UPDATED"


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
    action_create = "BIN_CREATED"
    required_read_permission = "organization.bins.view"
    required_write_permission = "organization.bins.manage"

    def _filter(self, request, rows):
        for key in ("warehouse_id", "zone_id", "section_id", "storage_type_id"):
            value = request.GET.get(key)
            if value:
                rows = rows.filter(**{key: value})
        return rows

    def _search(self, request, rows, search: str):
        return rows.filter(Q(bin_code__icontains=search) | Q(barcode__icontains=search))


class BinDetailView(HierarchyDetailView):
    model = Bin
    serializer = staticmethod(lambda item: serialize_bin(item))
    create_fields = BinListCreateView.create_fields
    action_update = "BIN_UPDATED"
    action_status = "BIN_BLOCKED"

    def patch(self, request, item_id):
        instance = get_object_or_404(self.model, id=item_id)
        was_blocked = instance.is_blocked
        response = super().patch(request, item_id)
        if response.status_code == 200 and "is_blocked" in request.data:
            instance.refresh_from_db()
            if instance.is_blocked != was_blocked:
                _audit(
                    request,
                    "BIN_BLOCKED" if instance.is_blocked else "BIN_UNBLOCKED",
                    instance._meta.model_name,
                    str(instance.pk),
                    after=self.serializer(instance),
                )
        return response


class HierarchyTreeView(APIView):
    permission_classes = [TenantAdminPermission]
    required_read_permission = "organization.hierarchy.view"
    throttle_scope = "standard_api"

    def get(self, request):
        plants = list(Plant.objects.order_by("plant_code"))
        warehouses = list(Warehouse.objects.order_by("code"))
        plant_rows = []
        for plant in plants:
            plant_warehouses = [warehouse for warehouse in warehouses if warehouse.plant_id == plant.id]
            plant_rows.append(
                {
                    **serialize_plant(plant),
                    "warehouses": [_warehouse_tree(warehouse) for warehouse in plant_warehouses],
                }
            )
        direct_warehouses = [warehouse for warehouse in warehouses if warehouse.plant_id is None]
        return JsonResponse(
            {
                "plants": plant_rows,
                "direct_warehouses": [_warehouse_tree(warehouse) for warehouse in direct_warehouses],
            }
        )


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
        "created_by_user_id": str(plant.created_by_user_id) if plant.created_by_user_id else None,
        "updated_by_user_id": str(plant.updated_by_user_id) if plant.updated_by_user_id else None,
    }


def serialize_product_category(category: ProductCategory) -> dict[str, Any]:
    return {
        "id": str(category.id),
        "category_code": category.category_code,
        "name": category.name,
        "description": category.description,
        "parent_category_id": str(category.parent_category_id) if category.parent_category_id else None,
        "parent_category_code": category.parent_category.category_code if category.parent_category_id else "",
        "status": category.status,
        "created_at": category.created_at.isoformat(),
        "updated_at": category.updated_at.isoformat(),
        "created_by_user_id": str(category.created_by_user_id) if category.created_by_user_id else None,
        "updated_by_user_id": str(category.updated_by_user_id) if category.updated_by_user_id else None,
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
        "created_by_user_id": str(warehouse.created_by_user_id) if warehouse.created_by_user_id else None,
        "updated_by_user_id": str(warehouse.updated_by_user_id) if warehouse.updated_by_user_id else None,
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
        "created_by_user_id": str(zone.created_by_user_id) if zone.created_by_user_id else None,
        "updated_by_user_id": str(zone.updated_by_user_id) if zone.updated_by_user_id else None,
    }


def serialize_storage_type(storage_type: StorageType) -> dict[str, Any]:
    return {
        "id": str(storage_type.id),
        "warehouse_id": str(storage_type.warehouse_id),
        "storage_type_code": storage_type.storage_type_code,
        "name": storage_type.name,
        "status": storage_type.status,
        "created_by_user_id": str(storage_type.created_by_user_id) if storage_type.created_by_user_id else None,
        "updated_by_user_id": str(storage_type.updated_by_user_id) if storage_type.updated_by_user_id else None,
    }


def serialize_section(section: StorageSection) -> dict[str, Any]:
    return {
        "id": str(section.id),
        "warehouse_id": str(section.warehouse_id),
        "zone_id": str(section.zone_id),
        "storage_type_id": str(section.storage_type_id) if section.storage_type_id else None,
        "section_code": section.section_code,
        "name": section.name,
        "status": section.status,
        "sequence": section.sequence,
        "created_by_user_id": str(section.created_by_user_id) if section.created_by_user_id else None,
        "updated_by_user_id": str(section.updated_by_user_id) if section.updated_by_user_id else None,
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
        "created_by_user_id": str(bin_.created_by_user_id) if bin_.created_by_user_id else None,
        "updated_by_user_id": str(bin_.updated_by_user_id) if bin_.updated_by_user_id else None,
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


def _is_duplicate_validation(exc: ValidationError) -> bool:
    messages = exc.message_dict if hasattr(exc, "message_dict") else {"__all__": exc.messages}
    return "unique" in str(messages).lower() or "already exists" in str(messages).lower()


def _warehouse_tree(warehouse: Warehouse) -> dict[str, Any]:
    zones = list(Zone.objects.filter(warehouse=warehouse).order_by("sequence", "zone_code"))
    storage_types = list(StorageType.objects.filter(warehouse=warehouse).order_by("storage_type_code"))
    sections = list(StorageSection.objects.filter(warehouse=warehouse).order_by("sequence", "section_code"))
    bins = list(Bin.objects.filter(warehouse=warehouse).order_by("bin_code"))
    return {
        **serialize_warehouse(warehouse),
        "zones": [serialize_zone(zone) for zone in zones],
        "storage_types": [serialize_storage_type(storage_type) for storage_type in storage_types],
        "sections": [serialize_section(section) for section in sections],
        "bins": [serialize_bin(bin_) for bin_ in bins],
    }
