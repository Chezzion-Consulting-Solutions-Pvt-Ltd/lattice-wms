from __future__ import annotations

import csv
import io
import json
from typing import Any

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from audit.models import AuditEvent
from control.models import Tenant, TenantMembership
from identity.authorization import has_permission
from identity.models import WarehouseAssignment
from tenancy.context import get_tenant_context
from warehouse.models import (
    Bay,
    Container,
    HoldingUnit,
    InventoryCategory,
    InventoryMetadata,
    LifecycleStatus,
    Machine,
    MissionDefinition,
    MissionGroup,
    OperationDefinition,
    OrderDefinition,
    Pallet,
    PeopleResource,
    Plant,
    ProductCategory,
    SequenceNumber,
    SkuGrouping,
    StatusDefinition,
    StockKeepingUnit,
    StorageSection,
    StorageType,
    Truck,
    Vehicle,
    Warehouse,
    WarehouseControl,
    WarehouseLog,
    Zone,
    ZoneQueue,
)
from warehouse.services import BayBulkCreationService, SequenceService


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
                    "bays": Bay.objects.count(),
                    "active_bays": Bay.objects.filter(status=LifecycleStatus.ACTIVE, is_blocked=False).count(),
                    "blocked_bays": Bay.objects.filter(is_blocked=True).count(),
                    "machines": Machine.objects.count(),
                    "people_resources": PeopleResource.objects.count(),
                    "configuration_alerts": int(not Warehouse.objects.filter(status=LifecycleStatus.ACTIVE, is_active=True).exists()) + Bay.objects.filter(is_blocked=True).count() + StorageType.objects.filter(is_active=False).count(),
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
        rows = self._warehouse_scope(request, rows)
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
        if isinstance(instance, Bay) and "bay_code" in request.data and "bin_code" not in request.data:
            request.data["bin_code"] = request.data["bay_code"]
        for field in self.create_fields:
            if field in request.data:
                setattr(instance, field, request.data[field])
        if not _has_warehouse_assignment(request, _warehouse_code_for_instance(instance)):
            return _error("WAREHOUSE_ACCESS_DENIED", "Warehouse access denied.", 403)
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

    def _warehouse_scope(self, request, rows):
        return _apply_warehouse_scope(request, rows, self.model)


class HierarchyDetailView(HierarchyListCreateView):
    action_update = ""
    action_status = ""

    def get(self, request, item_id):
        instance = get_object_or_404(self.model, id=item_id)
        if not _has_warehouse_assignment(request, _warehouse_code_for_instance(instance)):
            return _error("WAREHOUSE_ACCESS_DENIED", "Warehouse access denied.", 403)
        return JsonResponse(self.serializer(instance))

    def patch(self, request, item_id):
        instance = get_object_or_404(self.model, id=item_id)
        if not _has_warehouse_assignment(request, _warehouse_code_for_instance(instance)):
            return _error("WAREHOUSE_ACCESS_DENIED", "Warehouse access denied.", 403)
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
    create_fields = (
        "warehouse_id",
        "storage_type_code",
        "name",
        "description",
        "status",
        "capacity_rules",
        "handling_rules",
        "storage_behavior",
        "temperature_class",
        "hazard_class",
        "capacity_method",
        "putaway_allowed",
        "picking_allowed",
        "count_allowed",
        "mixed_sku_allowed",
        "mixed_batch_allowed",
        "mixed_hu_allowed",
        "display_order",
    )
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
    create_fields = ("warehouse_id", "zone_id", "storage_type_id", "section_code", "name", "status", "aisle_from", "aisle_to", "sequence", "description")
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


class BayListCreateView(HierarchyListCreateView):
    model = Bay
    serializer = staticmethod(lambda item: serialize_bay(item))
    create_fields = (
        "warehouse_id",
        "zone_id",
        "storage_type_id",
        "section_id",
        "bin_code",
        "name",
        "barcode",
        "external_reference",
        "status",
        "aisle",
        "rack",
        "level",
        "position",
        "bay_type",
        "x_coordinate",
        "y_coordinate",
        "z_coordinate",
        "length",
        "width",
        "height",
        "max_weight",
        "max_volume",
        "max_pallets",
        "max_hu_count",
        "temperature_class",
        "hazard_class",
        "mixed_sku_allowed",
        "mixed_batch_allowed",
        "mixed_inventory_category_allowed",
        "is_pickable",
        "is_putaway_allowed",
        "count_allowed",
        "replenishment_allowed",
        "is_blocked",
        "block_reason",
        "is_countable",
        "sequence",
    )
    action_create = "BAY_CREATED"
    required_read_permission = "tenant.bays.view"
    required_write_permission = "tenant.bays.manage"

    def _filter(self, request, rows):
        for key in ("warehouse_id", "zone_id", "section_id", "storage_type_id"):
            value = request.GET.get(key)
            if value:
                rows = rows.filter(**{key: value})
        return rows

    def _search(self, request, rows, search: str):
        return rows.filter(Q(bin_code__icontains=search) | Q(barcode__icontains=search))


class BayDetailView(HierarchyDetailView):
    model = Bay
    serializer = staticmethod(lambda item: serialize_bay(item))
    create_fields = BayListCreateView.create_fields
    action_update = "BAY_UPDATED"
    action_status = "BAY_STATUS_CHANGED"

    def patch(self, request, item_id):
        instance = get_object_or_404(self.model, id=item_id)
        was_blocked = instance.is_blocked
        response = super().patch(request, item_id)
        if response.status_code == 200 and "is_blocked" in request.data:
            instance.refresh_from_db()
            if instance.is_blocked != was_blocked:
                _audit(
                    request,
                    "BAY_BLOCKED" if instance.is_blocked else "BAY_UNBLOCKED",
                    instance._meta.model_name,
                    str(instance.pk),
                    after=self.serializer(instance),
                )
        return response


class BinListCreateView(BayListCreateView):
    action_create = "BAY_CREATED"


class BinDetailView(BayDetailView):
    pass


class BayBulkView(APIView):
    permission_classes = [TenantAdminPermission]
    required_read_permission = "tenant.bays.view"
    required_write_permission = "tenant.bays.bulk_create"
    throttle_scope = "standard_api"

    def post(self, request):
        if not _has_warehouse_assignment(request, _warehouse_code_from_id(request.data.get("warehouse_id"))):
            return _error("WAREHOUSE_ACCESS_DENIED", "Warehouse access denied.", 403)
        service = BayBulkCreationService()
        try:
            result = service.commit(request.data) if request.data.get("commit") is True else service.preview(request.data)
        except (KeyError, ValueError, Warehouse.DoesNotExist, Zone.DoesNotExist, StorageType.DoesNotExist, StorageSection.DoesNotExist) as exc:
            return _error("VALIDATION_ERROR", str(exc), 400)
        if result["validation_failures"]:
            return _error("VALIDATION_ERROR", result, 400)
        if request.data.get("commit") is True:
            _audit(request, "BAY_BULK_CREATED", "bay", "", after={"created": result["created"], "warehouse_code": _warehouse_code_from_id(request.data.get("warehouse_id"))})
        return JsonResponse(result, status=201 if request.data.get("commit") is True else 200)


class BayImportView(APIView):
    permission_classes = [TenantAdminPermission]
    required_read_permission = "tenant.bays.view"
    required_write_permission = "tenant.bays.import"
    throttle_scope = "standard_api"

    def post(self, request):
        rows = request.data.get("rows")
        if rows is None and request.data.get("csv"):
            rows = list(csv.DictReader(io.StringIO(str(request.data.get("csv")))))
        if not isinstance(rows, list):
            return _error("VALIDATION_ERROR", "rows must be a list or csv must be provided.", 400)
        failures = []
        prepared = []
        for index, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                failures.append({"row": index, "error": "row must be an object"})
                continue
            warehouse_code = _warehouse_code_from_id(row.get("warehouse_id"))
            if not _has_warehouse_assignment(request, warehouse_code):
                failures.append({"row": index, "error": "warehouse access denied"})
                continue
            data = {**row}
            if "bay_code" in data and "bin_code" not in data:
                data["bin_code"] = data["bay_code"]
            prepared.append(data)
        if failures:
            return _error("VALIDATION_ERROR", {"failures": failures}, 400)
        if request.data.get("commit") is not True:
            return JsonResponse({"count": len(prepared), "sample": prepared[:25], "validation_failures": []})
        created = 0
        with transaction.atomic(using=get_tenant_context().database_alias):
            for data in prepared:
                bay = Bay()
                for field in BayListCreateView.create_fields:
                    if field in data:
                        setattr(bay, field, data[field])
                bay.full_clean()
                bay.save()
                created += 1
        _audit(request, "BAY_IMPORT_COMPLETED", "bay", "", after={"created": created})
        return JsonResponse({"created": created}, status=201)


class BayExportView(APIView):
    permission_classes = [TenantAdminPermission]
    required_read_permission = "tenant.bays.export"
    throttle_scope = "standard_api"

    def get(self, request):
        rows = _apply_warehouse_scope(request, Bay.objects.all().order_by("warehouse__code", "bin_code"), Bay)
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="lattice-bays.csv"'
        writer = csv.writer(response)
        writer.writerow(["bay_code", "warehouse_id", "zone_id", "section_id", "storage_type_id", "barcode", "aisle", "rack", "level", "position", "status"])
        for bay in rows:
            writer.writerow([_csv_safe(value) for value in [bay.bin_code, bay.warehouse_id, bay.zone_id, bay.section_id or "", bay.storage_type_id or "", bay.barcode, bay.aisle, bay.rack, bay.level, bay.position, bay.status]])
        _audit(request, "BAY_EXPORT_CREATED", "bay", "", after={"count": rows.count()})
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
        "description": storage_type.description,
        "status": storage_type.status,
        "storage_behavior": storage_type.storage_behavior,
        "temperature_class": storage_type.temperature_class,
        "hazard_class": storage_type.hazard_class,
        "capacity_method": storage_type.capacity_method,
        "putaway_allowed": storage_type.putaway_allowed,
        "picking_allowed": storage_type.picking_allowed,
        "count_allowed": storage_type.count_allowed,
        "mixed_sku_allowed": storage_type.mixed_sku_allowed,
        "mixed_batch_allowed": storage_type.mixed_batch_allowed,
        "mixed_hu_allowed": storage_type.mixed_hu_allowed,
        "display_order": storage_type.display_order,
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
        "aisle_from": section.aisle_from,
        "aisle_to": section.aisle_to,
        "sequence": section.sequence,
        "created_by_user_id": str(section.created_by_user_id) if section.created_by_user_id else None,
        "updated_by_user_id": str(section.updated_by_user_id) if section.updated_by_user_id else None,
    }


def serialize_bay(bay: Bay) -> dict[str, Any]:
    return {
        "id": str(bay.id),
        "warehouse_id": str(bay.warehouse_id),
        "zone_id": str(bay.zone_id),
        "storage_type_id": str(bay.storage_type_id) if bay.storage_type_id else None,
        "section_id": str(bay.section_id) if bay.section_id else None,
        "bay_code": bay.bin_code,
        "bin_code": bay.bin_code,
        "name": bay.name,
        "barcode": bay.barcode,
        "external_reference": bay.external_reference,
        "status": bay.status,
        "aisle": bay.aisle,
        "rack": bay.rack,
        "bay": bay.rack,
        "level": bay.level,
        "position": bay.position,
        "bay_type": bay.bay_type,
        "x_coordinate": str(bay.x_coordinate) if bay.x_coordinate is not None else None,
        "y_coordinate": str(bay.y_coordinate) if bay.y_coordinate is not None else None,
        "z_coordinate": str(bay.z_coordinate) if bay.z_coordinate is not None else None,
        "length": str(bay.length) if bay.length is not None else None,
        "width": str(bay.width) if bay.width is not None else None,
        "height": str(bay.height) if bay.height is not None else None,
        "max_weight": str(bay.max_weight) if bay.max_weight is not None else None,
        "max_volume": str(bay.max_volume) if bay.max_volume is not None else None,
        "max_pallets": bay.max_pallets,
        "max_holding_units": bay.max_hu_count,
        "temperature_class": bay.temperature_class,
        "hazard_class": bay.hazard_class,
        "mixed_sku_allowed": bay.mixed_sku_allowed,
        "mixed_batch_allowed": bay.mixed_batch_allowed,
        "mixed_inventory_category_allowed": bay.mixed_inventory_category_allowed,
        "is_pickable": bay.is_pickable,
        "is_putaway_allowed": bay.is_putaway_allowed,
        "putaway_allowed": bay.is_putaway_allowed,
        "picking_allowed": bay.is_pickable,
        "count_allowed": bay.count_allowed,
        "replenishment_allowed": bay.replenishment_allowed,
        "is_blocked": bay.is_blocked,
        "block_reason": bay.block_reason,
        "is_countable": bay.is_countable,
        "sequence": bay.sequence,
        "created_by_user_id": str(bay.created_by_user_id) if bay.created_by_user_id else None,
        "updated_by_user_id": str(bay.updated_by_user_id) if bay.updated_by_user_id else None,
    }


class GenericConfigurationListCreateView(HierarchyListCreateView):
    required_read_permission = "tenant.configuration.view"
    required_write_permission = "tenant.configuration.manage"

    def _search(self, request, rows, search: str):
        query = Q(name__icontains=search)
        for field in self.create_fields:
            if field.endswith("_code") or field == "code":
                query |= Q(**{f"{field}__icontains": search})
        return rows.filter(query)


class GenericConfigurationDetailView(HierarchyDetailView):
    required_read_permission = "tenant.configuration.view"
    required_write_permission = "tenant.configuration.manage"


def _simple_serializer(code_key: str):
    def serializer(item) -> dict[str, Any]:
        payload = {
            "id": str(item.id),
            code_key: getattr(item, code_key),
            "name": item.name,
            "description": item.description,
            "is_active": item.is_active,
            "created_at": item.created_at.isoformat(),
            "updated_at": item.updated_at.isoformat(),
        }
        for key in (
            "warehouse_id",
            "zone_id",
            "default_zone_id",
            "plant_id",
            "scope",
            "process",
            "settings",
            "status",
            "priority",
            "sequence",
            "entity_type",
            "prefix",
            "suffix",
            "padding",
            "current_value",
            "min_value",
            "max_value",
            "reset_policy",
            "display_order",
            "color_token",
        ):
            if hasattr(item, key):
                value = getattr(item, key)
                payload[key] = str(value) if key.endswith("_id") and value is not None else value
        return payload

    return serializer


class HoldingUnitListCreateView(GenericConfigurationListCreateView):
    model = HoldingUnit
    serializer = staticmethod(_simple_serializer("hu_code"))
    create_fields = ("hu_code", "name", "description", "hu_type", "dimensions", "tare_weight", "max_weight", "max_volume", "stackable", "reusable", "is_active")
    action_create = "HU_TYPE_CREATED"


class HoldingUnitDetailView(GenericConfigurationDetailView, HoldingUnitListCreateView):
    action_update = "HU_TYPE_UPDATED"


class PalletListCreateView(GenericConfigurationListCreateView):
    model = Pallet
    serializer = staticmethod(_simple_serializer("pallet_code"))
    create_fields = ("pallet_code", "name", "description", "pallet_type", "length", "width", "height", "tare_weight", "max_weight", "max_volume", "stackable", "reusable", "is_active")
    action_create = "PALLET_TYPE_CREATED"


class PalletDetailView(GenericConfigurationDetailView, PalletListCreateView):
    action_update = "PALLET_TYPE_UPDATED"


class MachineListCreateView(GenericConfigurationListCreateView):
    model = Machine
    serializer = staticmethod(_simple_serializer("machine_code"))
    create_fields = ("machine_code", "name", "description", "machine_type", "warehouse_id", "zone_id", "manufacturer", "model", "serial_number", "capacity_metadata", "status", "is_active")
    action_create = "MACHINE_CREATED"


class MachineDetailView(GenericConfigurationDetailView, MachineListCreateView):
    action_update = "MACHINE_UPDATED"


class PeopleResourceListCreateView(GenericConfigurationListCreateView):
    model = PeopleResource
    serializer = staticmethod(_simple_serializer("resource_code"))
    create_fields = ("resource_code", "name", "description", "user_id", "warehouse_id", "resource_type", "qualification_metadata", "default_zone_id", "status", "is_active")
    action_create = "RESOURCE_CREATED"


class PeopleResourceDetailView(GenericConfigurationDetailView, PeopleResourceListCreateView):
    action_update = "RESOURCE_UPDATED"


class SkuGroupingListCreateView(GenericConfigurationListCreateView):
    model = SkuGrouping
    serializer = staticmethod(_simple_serializer("group_code"))
    create_fields = ("group_code", "name", "description", "grouping_type", "rules", "priority", "is_active")
    action_create = "SKU_GROUP_CREATED"


class SkuGroupingDetailView(GenericConfigurationDetailView, SkuGroupingListCreateView):
    action_update = "SKU_GROUP_UPDATED"


class InventoryCategoryListCreateView(GenericConfigurationListCreateView):
    model = InventoryCategory
    serializer = staticmethod(_simple_serializer("category_code"))
    create_fields = ("category_code", "name", "description", "category_type", "quality_restriction", "available_for_allocation", "is_active")
    action_create = "INVENTORY_CATEGORY_CREATED"


class InventoryCategoryDetailView(GenericConfigurationDetailView, InventoryCategoryListCreateView):
    action_update = "INVENTORY_CATEGORY_UPDATED"


class OperationDefinitionListCreateView(GenericConfigurationListCreateView):
    model = OperationDefinition
    serializer = staticmethod(_simple_serializer("operation_code"))
    create_fields = ("operation_code", "name", "description", "operation_type", "source_required", "destination_required", "scan_required", "confirmation_required", "sequence", "is_active")
    action_create = "OPERATION_DEFINITION_CREATED"


class OperationDefinitionDetailView(GenericConfigurationDetailView, OperationDefinitionListCreateView):
    action_update = "OPERATION_DEFINITION_UPDATED"


class MissionDefinitionListCreateView(GenericConfigurationListCreateView):
    model = MissionDefinition
    serializer = staticmethod(_simple_serializer("mission_code"))
    create_fields = ("mission_code", "name", "description", "mission_type", "code_pattern", "source_rules", "destination_rules", "priority_defaults", "zone_behavior", "status_scheme", "is_active")
    action_create = "MISSION_DEFINITION_CREATED"


class MissionDefinitionDetailView(GenericConfigurationDetailView, MissionDefinitionListCreateView):
    action_update = "MISSION_DEFINITION_UPDATED"


class MissionGroupListCreateView(GenericConfigurationListCreateView):
    model = MissionGroup
    serializer = staticmethod(_simple_serializer("group_code"))
    create_fields = ("group_code", "name", "description", "grouping_strategy", "max_missions", "priority", "is_active")
    action_create = "MISSION_GROUP_CREATED"


class MissionGroupDetailView(GenericConfigurationDetailView, MissionGroupListCreateView):
    action_update = "MISSION_GROUP_UPDATED"


class ZoneQueueListCreateView(GenericConfigurationListCreateView):
    model = ZoneQueue
    serializer = staticmethod(_simple_serializer("queue_code"))
    create_fields = ("queue_code", "name", "description", "warehouse_id", "zone_id", "priority", "sequence", "max_open_missions", "assignment_strategy", "is_active")
    action_create = "ZONE_QUEUE_CREATED"


class ZoneQueueDetailView(GenericConfigurationDetailView, ZoneQueueListCreateView):
    action_update = "ZONE_QUEUE_UPDATED"


class SequenceListCreateView(GenericConfigurationListCreateView):
    model = SequenceNumber
    serializer = staticmethod(_simple_serializer("sequence_code"))
    create_fields = ("sequence_code", "name", "description", "entity_type", "warehouse_id", "prefix", "suffix", "padding", "current_value", "min_value", "max_value", "reset_policy", "is_active")
    action_create = "SEQUENCE_CREATED"


class SequenceDetailView(GenericConfigurationDetailView, SequenceListCreateView):
    action_update = "SEQUENCE_UPDATED"


class SequenceActionView(APIView):
    permission_classes = [TenantAdminPermission]
    required_read_permission = "tenant.configuration.view"
    required_write_permission = "tenant.configuration.manage"
    throttle_scope = "standard_api"

    def post(self, request, item_id, action):
        sequence = get_object_or_404(SequenceNumber, id=item_id)
        if not _has_warehouse_assignment(request, _warehouse_code_for_instance(sequence)):
            return _error("WAREHOUSE_ACCESS_DENIED", "Warehouse access denied.", 403)
        service = SequenceService()
        try:
            if action == "preview":
                value = service.preview(sequence)
            elif action == "reserve":
                value = service.reserve(str(sequence.id))
            elif action == "reset":
                value = service.reset(str(sequence.id))
            else:
                return _error("UNKNOWN_ACTION", "Unknown sequence action.", 404)
        except ValueError as exc:
            return _error("VALIDATION_ERROR", str(exc), 400)
        _audit(request, f"SEQUENCE_{action.upper()}", "sequence", str(sequence.id), after={"value": value})
        return JsonResponse({"value": value})


class StatusDefinitionListCreateView(GenericConfigurationListCreateView):
    model = StatusDefinition
    serializer = staticmethod(_simple_serializer("status_code"))
    create_fields = ("status_code", "name", "description", "entity_type", "is_initial", "is_terminal", "display_order", "color_token", "allowed_transitions", "is_active")
    action_create = "STATUS_DEFINITION_CREATED"


class StatusDefinitionDetailView(GenericConfigurationDetailView, StatusDefinitionListCreateView):
    action_update = "STATUS_DEFINITION_UPDATED"


class WarehouseControlListCreateView(GenericConfigurationListCreateView):
    model = WarehouseControl
    serializer = staticmethod(_simple_serializer("scope"))
    create_fields = ("name", "description", "plant_id", "warehouse_id", "scope", "process", "settings", "is_active")
    action_create = "WAREHOUSE_CONTROL_UPDATED"


class WarehouseControlDetailView(GenericConfigurationDetailView, WarehouseControlListCreateView):
    action_update = "WAREHOUSE_CONTROL_UPDATED"


class TruckListCreateView(GenericConfigurationListCreateView):
    model = Truck
    serializer = staticmethod(_simple_serializer("code"))
    create_fields = ("code", "name", "description", "configuration_type", "capacity", "dimensions", "identifier_metadata", "is_active")
    action_create = "TRUCK_CONFIGURATION_CREATED"


class TruckDetailView(GenericConfigurationDetailView, TruckListCreateView):
    action_update = "TRUCK_CONFIGURATION_UPDATED"


class ContainerListCreateView(TruckListCreateView):
    model = Container
    action_create = "CONTAINER_CONFIGURATION_CREATED"


class ContainerDetailView(GenericConfigurationDetailView, ContainerListCreateView):
    action_update = "CONTAINER_CONFIGURATION_UPDATED"


class VehicleListCreateView(TruckListCreateView):
    model = Vehicle
    action_create = "VEHICLE_CONFIGURATION_CREATED"


class VehicleDetailView(GenericConfigurationDetailView, VehicleListCreateView):
    action_update = "VEHICLE_CONFIGURATION_UPDATED"


def _membership(request):
    context = get_tenant_context()
    return TenantMembership.objects.filter(user=request.user, tenant_id=context.tenant_id, status=TenantMembership.Status.ACTIVE).first()


def _audit(request, action: str, resource_type: str, resource_id: str, *, before=None, after=None):
    context = get_tenant_context()
    warehouse_code = None
    if isinstance(after, dict):
        warehouse_code = after.get("warehouse_code")
    warehouse = Warehouse.objects.filter(code=warehouse_code).first() if warehouse_code else None
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
    WarehouseLog.objects.create(
        actor_user_id=request.user.id,
        action=action,
        entity_type=resource_type,
        entity_id=resource_id,
        warehouse=warehouse,
        request_id=getattr(request, "request_id", ""),
        result="SUCCESS",
        metadata=_safe_json({"before": before or {}, "after": after or {}}),
    )


def _safe_json(value):
    return json.loads(json.dumps(value, default=str))


def _csv_safe(value) -> str:
    text = str(value)
    return f"'{text}" if text.startswith(("=", "+", "-", "@")) else text


def _error(code: str, message, status_code: int) -> JsonResponse:
    return JsonResponse({"error": {"code": code, "message": message}}, status=status_code)


def _is_duplicate_validation(exc: ValidationError) -> bool:
    messages = exc.message_dict if hasattr(exc, "message_dict") else {"__all__": exc.messages}
    return "unique" in str(messages).lower() or "already exists" in str(messages).lower()


def _warehouse_tree(warehouse: Warehouse) -> dict[str, Any]:
    zones = list(Zone.objects.filter(warehouse=warehouse).order_by("sequence", "zone_code"))
    storage_types = list(StorageType.objects.filter(warehouse=warehouse).order_by("storage_type_code"))
    sections = list(StorageSection.objects.filter(warehouse=warehouse).order_by("sequence", "section_code"))
    bays = list(Bay.objects.filter(warehouse=warehouse).order_by("bin_code"))
    return {
        **serialize_warehouse(warehouse),
        "zones": [serialize_zone(zone) for zone in zones],
        "storage_types": [serialize_storage_type(storage_type) for storage_type in storage_types],
        "sections": [serialize_section(section) for section in sections],
        "bays": [serialize_bay(bay) for bay in bays],
        "bins": [serialize_bay(bay) for bay in bays],
    }


def _assigned_warehouse_codes(request) -> set[str]:
    membership = _membership(request)
    if membership is None:
        return set()
    return set(membership.warehouse_assignments.filter(is_active=True).values_list("warehouse_code", flat=True))


def _has_warehouse_assignment(request, warehouse_code: str | None) -> bool:
    if warehouse_code is None:
        return True
    codes = _assigned_warehouse_codes(request)
    return "*" in codes or warehouse_code in codes


def _warehouse_code_for_instance(instance) -> str | None:
    if isinstance(instance, Warehouse):
        return None if instance._state.adding else instance.code
    warehouse = getattr(instance, "warehouse", None)
    if warehouse is not None:
        return warehouse.code
    warehouse_id = getattr(instance, "warehouse_id", None)
    if warehouse_id:
        return Warehouse.objects.filter(id=warehouse_id).values_list("code", flat=True).first()
    return None


def _warehouse_code_from_id(warehouse_id) -> str | None:
    if not warehouse_id:
        return None
    return Warehouse.objects.filter(id=warehouse_id).values_list("code", flat=True).first()


def _apply_warehouse_scope(request, rows, model):
    has_warehouse = any(field.name == "warehouse" for field in model._meta.fields)
    if model is Plant or not has_warehouse:
        if model is Warehouse:
            codes = _assigned_warehouse_codes(request)
            if "*" in codes:
                return rows
            return rows.filter(code__in=codes)
        return rows
    codes = _assigned_warehouse_codes(request)
    if "*" in codes:
        return rows
    return rows.filter(warehouse__code__in=codes)
