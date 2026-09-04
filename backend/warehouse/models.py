from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone as django_timezone


class LifecycleStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    INACTIVE = "INACTIVE", "Inactive"
    BLOCKED = "BLOCKED", "Blocked"
    ARCHIVED = "ARCHIVED", "Archived"


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(default=django_timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Plant(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plant_code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=24, choices=LifecycleStatus.choices, default=LifecycleStatus.ACTIVE)
    address_line_1 = models.CharField(max_length=180, blank=True)
    address_line_2 = models.CharField(max_length=180, blank=True)
    city = models.CharField(max_length=120, blank=True)
    state = models.CharField(max_length=120, blank=True)
    postal_code = models.CharField(max_length=32, blank=True)
    country = models.CharField(max_length=2, blank=True)
    timezone = models.CharField(max_length=64, default="UTC")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    contact_name = models.CharField(max_length=160, blank=True)
    contact_phone = models.CharField(max_length=40, blank=True)
    contact_email = models.EmailField(blank=True)
    created_by_user_id = models.UUIDField(null=True, blank=True)
    updated_by_user_id = models.UUIDField(null=True, blank=True)

    def __str__(self) -> str:
        return self.plant_code

    class Meta:
        db_table = "lattice_plant"


class Warehouse(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=160)
    is_active = models.BooleanField(default=True)
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name="warehouses", null=True, blank=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=24, choices=LifecycleStatus.choices, default=LifecycleStatus.ACTIVE)
    warehouse_type = models.CharField(max_length=40, blank=True)
    timezone = models.CharField(max_length=64, default="UTC")
    address_line_1 = models.CharField(max_length=180, blank=True)
    address_line_2 = models.CharField(max_length=180, blank=True)
    city = models.CharField(max_length=120, blank=True)
    state = models.CharField(max_length=120, blank=True)
    postal_code = models.CharField(max_length=32, blank=True)
    country = models.CharField(max_length=2, blank=True)
    capacity_metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=django_timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    created_by_user_id = models.UUIDField(null=True, blank=True)
    updated_by_user_id = models.UUIDField(null=True, blank=True)

    @property
    def warehouse_code(self) -> str:
        return self.code

    class Meta:
        db_table = "lattice_whs"


class ProductCategory(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category_code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    parent_category = models.ForeignKey("self", on_delete=models.PROTECT, related_name="child_categories", null=True, blank=True)
    status = models.CharField(max_length=24, choices=LifecycleStatus.choices, default=LifecycleStatus.ACTIVE)
    created_by_user_id = models.UUIDField(null=True, blank=True)
    updated_by_user_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "lattice_product_category"
        ordering = ["category_code"]

    def __str__(self) -> str:
        return self.category_code

    def clean(self):
        if not self.parent_category_id:
            return
        if self.pk and self.parent_category_id == self.pk:
            raise ValidationError({"parent_category": "Category cannot be its own parent."})
        ancestor = self.parent_category
        seen = {self.pk} if self.pk else set()
        while ancestor is not None:
            if ancestor.pk in seen:
                raise ValidationError({"parent_category": "Category hierarchy cannot contain a cycle."})
            seen.add(ancestor.pk)
            ancestor = ancestor.parent_category


class WarehouseScopedObject(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    external_reference = models.CharField(max_length=120, blank=True)

    class Meta:
        abstract = True


class WarehouseProbeObject(WarehouseScopedObject):
    """Minimal tenant object used by isolation tests before WMS modules exist."""

    pass

    class Meta:
        db_table = "lattice_probe"


class Zone(TimeStampedModel):
    class ZoneType(models.TextChoices):
        RECEIVING = "RECEIVING", "Receiving"
        STAGING = "STAGING", "Staging"
        QA = "QA", "QA"
        QUARANTINE = "QUARANTINE", "Quarantine"
        STORAGE = "STORAGE", "Storage"
        PICKING = "PICKING", "Picking"
        PACKING = "PACKING", "Packing"
        DISPATCH = "DISPATCH", "Dispatch"
        RETURNS = "RETURNS", "Returns"
        DAMAGED = "DAMAGED", "Damaged"
        BLOCKED = "BLOCKED", "Blocked"
        CUSTOM = "CUSTOM", "Custom"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="zones")
    zone_code = models.CharField(max_length=40)
    name = models.CharField(max_length=160)
    zone_type = models.CharField(max_length=24, choices=ZoneType.choices, default=ZoneType.STORAGE)
    status = models.CharField(max_length=24, choices=LifecycleStatus.choices, default=LifecycleStatus.ACTIVE)
    description = models.TextField(blank=True)
    sequence = models.PositiveIntegerField(default=0)
    created_by_user_id = models.UUIDField(null=True, blank=True)
    updated_by_user_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "lattice_zone"
        constraints = [models.UniqueConstraint(fields=["warehouse", "zone_code"], name="unique_zone_code_per_warehouse")]


class StorageType(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="storage_types")
    storage_type_code = models.CharField(max_length=40)
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=24, choices=LifecycleStatus.choices, default=LifecycleStatus.ACTIVE)
    capacity_rules = models.JSONField(default=dict, blank=True)
    handling_rules = models.JSONField(default=dict, blank=True)
    storage_behavior = models.CharField(max_length=40, default="RACK")
    temperature_class = models.CharField(max_length=40, blank=True)
    hazard_class = models.CharField(max_length=40, blank=True)
    capacity_method = models.CharField(max_length=40, default="NONE")
    putaway_allowed = models.BooleanField(default=True)
    picking_allowed = models.BooleanField(default=True)
    count_allowed = models.BooleanField(default=True)
    mixed_sku_allowed = models.BooleanField(default=False)
    mixed_batch_allowed = models.BooleanField(default=False)
    mixed_hu_allowed = models.BooleanField(default=False)
    display_order = models.PositiveIntegerField(default=0)
    created_by_user_id = models.UUIDField(null=True, blank=True)
    updated_by_user_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "lattice_stype"
        constraints = [models.UniqueConstraint(fields=["warehouse", "storage_type_code"], name="unique_storage_type_code_per_warehouse")]


class StorageSection(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="sections")
    zone = models.ForeignKey(Zone, on_delete=models.PROTECT, related_name="sections")
    storage_type = models.ForeignKey(StorageType, on_delete=models.PROTECT, related_name="sections", null=True, blank=True)
    section_code = models.CharField(max_length=40)
    name = models.CharField(max_length=160)
    status = models.CharField(max_length=24, choices=LifecycleStatus.choices, default=LifecycleStatus.ACTIVE)
    aisle_from = models.CharField(max_length=40, blank=True)
    aisle_to = models.CharField(max_length=40, blank=True)
    sequence = models.PositiveIntegerField(default=0)
    description = models.TextField(blank=True)
    created_by_user_id = models.UUIDField(null=True, blank=True)
    updated_by_user_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "lattice_section"
        constraints = [models.UniqueConstraint(fields=["warehouse", "section_code"], name="unique_section_code_per_warehouse")]

    def clean(self):
        if self.zone_id and self.zone.warehouse_id != self.warehouse_id:
            raise ValidationError({"zone": "Zone must belong to the selected warehouse."})
        if self.storage_type_id and self.storage_type.warehouse_id != self.warehouse_id:
            raise ValidationError({"storage_type": "Storage type must belong to the selected warehouse."})


class Bay(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="bays")
    zone = models.ForeignKey(Zone, on_delete=models.PROTECT, related_name="bays")
    storage_type = models.ForeignKey(StorageType, on_delete=models.PROTECT, related_name="bays", null=True, blank=True)
    section = models.ForeignKey(StorageSection, on_delete=models.PROTECT, related_name="bays", null=True, blank=True)
    bin_code = models.CharField(max_length=80)
    name = models.CharField(max_length=160, blank=True)
    barcode = models.CharField(max_length=120, blank=True)
    external_reference = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=24, choices=LifecycleStatus.choices, default=LifecycleStatus.ACTIVE)
    aisle = models.CharField(max_length=40, blank=True)
    rack = models.CharField(max_length=40, blank=True)
    level = models.CharField(max_length=40, blank=True)
    position = models.CharField(max_length=40, blank=True)
    bay_type = models.CharField(max_length=40, blank=True)
    x_coordinate = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    y_coordinate = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    z_coordinate = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    length = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    width = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    height = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    max_weight = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    max_volume = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    max_pallets = models.PositiveIntegerField(null=True, blank=True)
    max_hu_count = models.PositiveIntegerField(null=True, blank=True)
    temperature_class = models.CharField(max_length=40, blank=True)
    hazard_class = models.CharField(max_length=40, blank=True)
    mixed_sku_allowed = models.BooleanField(default=False)
    mixed_batch_allowed = models.BooleanField(default=False)
    mixed_inventory_category_allowed = models.BooleanField(default=False)
    is_pickable = models.BooleanField(default=True)
    is_putaway_allowed = models.BooleanField(default=True)
    count_allowed = models.BooleanField(default=True)
    replenishment_allowed = models.BooleanField(default=True)
    is_blocked = models.BooleanField(default=False)
    block_reason = models.CharField(max_length=240, blank=True)
    is_countable = models.BooleanField(default=True)
    sequence = models.PositiveIntegerField(default=0)
    created_by_user_id = models.UUIDField(null=True, blank=True)
    updated_by_user_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "lattice_bay"
        constraints = [
            models.UniqueConstraint(fields=["warehouse", "bin_code"], name="unique_bin_code_per_warehouse"),
            models.UniqueConstraint(fields=["warehouse", "barcode"], condition=~models.Q(barcode=""), name="unique_bin_barcode_per_warehouse"),
        ]

    def clean(self):
        if self.zone_id and self.zone.warehouse_id != self.warehouse_id:
            raise ValidationError({"zone": "Zone must belong to the selected warehouse."})
        if self.storage_type_id and self.storage_type.warehouse_id != self.warehouse_id:
            raise ValidationError({"storage_type": "Storage type must belong to the selected warehouse."})
        if self.section_id and self.section.warehouse_id != self.warehouse_id:
            raise ValidationError({"section": "Section must belong to the selected warehouse."})
        if self.section_id and self.section.zone_id != self.zone_id:
            raise ValidationError({"section": "Section must belong to the selected zone."})
        if self.is_blocked:
            self.status = LifecycleStatus.BLOCKED


class TenantConfigurationModel(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by_user_id = models.UUIDField(null=True, blank=True)
    updated_by_user_id = models.UUIDField(null=True, blank=True)

    class Meta:
        abstract = True


class HoldingUnit(TenantConfigurationModel):
    hu_code = models.CharField(max_length=40, unique=True)
    hu_type = models.CharField(max_length=40, default="CUSTOM")
    dimensions = models.JSONField(default=dict, blank=True)
    tare_weight = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    max_weight = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    max_volume = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    stackable = models.BooleanField(default=True)
    reusable = models.BooleanField(default=True)

    class Meta:
        db_table = "lattice_hu"


class Pallet(TenantConfigurationModel):
    pallet_code = models.CharField(max_length=40, unique=True)
    pallet_type = models.CharField(max_length=40, default="CUSTOM")
    length = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    width = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    height = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    tare_weight = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    max_weight = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    max_volume = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    stackable = models.BooleanField(default=True)
    reusable = models.BooleanField(default=True)

    class Meta:
        db_table = "lattice_pall"


class Machine(TenantConfigurationModel):
    machine_code = models.CharField(max_length=40, unique=True)
    machine_type = models.CharField(max_length=40, default="CUSTOM")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="machines")
    zone = models.ForeignKey(Zone, on_delete=models.PROTECT, related_name="machines", null=True, blank=True)
    manufacturer = models.CharField(max_length=120, blank=True)
    model = models.CharField(max_length=120, blank=True)
    serial_number = models.CharField(max_length=120, blank=True)
    capacity_metadata = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=24, choices=LifecycleStatus.choices, default=LifecycleStatus.ACTIVE)

    class Meta:
        db_table = "lattice_mach"

    def clean(self):
        if self.zone_id and self.zone.warehouse_id != self.warehouse_id:
            raise ValidationError({"zone": "Zone must belong to the selected warehouse."})


class PeopleResource(TenantConfigurationModel):
    resource_code = models.CharField(max_length=40, unique=True)
    user_id = models.UUIDField(null=True, blank=True)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="people_resources")
    resource_type = models.CharField(max_length=40, default="CUSTOM")
    qualification_metadata = models.JSONField(default=dict, blank=True)
    default_zone = models.ForeignKey(Zone, on_delete=models.PROTECT, related_name="people_resources", null=True, blank=True)
    status = models.CharField(max_length=24, choices=LifecycleStatus.choices, default=LifecycleStatus.ACTIVE)

    class Meta:
        db_table = "lattice_ppl"

    def clean(self):
        if self.default_zone_id and self.default_zone.warehouse_id != self.warehouse_id:
            raise ValidationError({"default_zone": "Default zone must belong to the selected warehouse."})


class SkuGrouping(TenantConfigurationModel):
    group_code = models.CharField(max_length=40, unique=True)
    grouping_type = models.CharField(max_length=40, default="CUSTOM")
    rules = models.JSONField(default=dict, blank=True)
    priority = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "lattice_skugrp"


class InventoryCategory(TenantConfigurationModel):
    category_code = models.CharField(max_length=40, unique=True)
    category_type = models.CharField(max_length=40, default="CUSTOM")
    quality_restriction = models.JSONField(default=dict, blank=True)
    available_for_allocation = models.BooleanField(default=True)

    class Meta:
        db_table = "lattice_invcat"


class OperationDefinition(TenantConfigurationModel):
    operation_code = models.CharField(max_length=40, unique=True)
    operation_type = models.CharField(max_length=40, default="CUSTOM")
    source_required = models.BooleanField(default=False)
    destination_required = models.BooleanField(default=False)
    scan_required = models.BooleanField(default=True)
    confirmation_required = models.BooleanField(default=True)
    sequence = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "lattice_oper"


class MissionDefinition(TenantConfigurationModel):
    mission_code = models.CharField(max_length=40, unique=True)
    mission_type = models.CharField(max_length=40, default="CUSTOM")
    code_pattern = models.CharField(max_length=120, blank=True)
    source_rules = models.JSONField(default=dict, blank=True)
    destination_rules = models.JSONField(default=dict, blank=True)
    priority_defaults = models.JSONField(default=dict, blank=True)
    zone_behavior = models.JSONField(default=dict, blank=True)
    status_scheme = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "lattice_misn"


class MissionGroup(TenantConfigurationModel):
    group_code = models.CharField(max_length=40, unique=True)
    grouping_strategy = models.CharField(max_length=40, default="CUSTOM")
    max_missions = models.PositiveIntegerField(null=True, blank=True)
    priority = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "lattice_grp"


class ZoneQueue(TenantConfigurationModel):
    queue_code = models.CharField(max_length=40, unique=True)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="zone_queues")
    zone = models.ForeignKey(Zone, on_delete=models.PROTECT, related_name="zone_queues")
    priority = models.PositiveIntegerField(default=0)
    sequence = models.PositiveIntegerField(default=0)
    max_open_missions = models.PositiveIntegerField(null=True, blank=True)
    assignment_strategy = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "lattice_zq"

    def clean(self):
        if self.zone_id and self.zone.warehouse_id != self.warehouse_id:
            raise ValidationError({"zone": "Zone must belong to the selected warehouse."})


class SequenceNumber(TenantConfigurationModel):
    sequence_code = models.CharField(max_length=40, unique=True)
    entity_type = models.CharField(max_length=80)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="sequences", null=True, blank=True)
    prefix = models.CharField(max_length=40, blank=True)
    suffix = models.CharField(max_length=40, blank=True)
    padding = models.PositiveIntegerField(default=6)
    current_value = models.PositiveBigIntegerField(default=0)
    min_value = models.PositiveBigIntegerField(default=1)
    max_value = models.PositiveBigIntegerField(null=True, blank=True)
    reset_policy = models.CharField(max_length=40, default="NEVER")
    last_reset_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "lattice_seq"


class StatusDefinition(TenantConfigurationModel):
    status_code = models.CharField(max_length=40)
    entity_type = models.CharField(max_length=80)
    is_initial = models.BooleanField(default=False)
    is_terminal = models.BooleanField(default=False)
    display_order = models.PositiveIntegerField(default=0)
    color_token = models.CharField(max_length=40, blank=True)
    allowed_transitions = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "lattice_status"
        constraints = [models.UniqueConstraint(fields=["entity_type", "status_code"], name="unique_status_per_entity")]


class TransportConfiguration(TenantConfigurationModel):
    code = models.CharField(max_length=40, unique=True)
    configuration_type = models.CharField(max_length=40, default="CUSTOM")
    capacity = models.JSONField(default=dict, blank=True)
    dimensions = models.JSONField(default=dict, blank=True)
    identifier_metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        abstract = True


class Truck(TransportConfiguration):
    class Meta:
        db_table = "lattice_truck"


class Container(TransportConfiguration):
    class Meta:
        db_table = "lattice_ctnr"


class Vehicle(TransportConfiguration):
    class Meta:
        db_table = "lattice_veh"


class WarehouseControl(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=160, default="Warehouse Control")
    description = models.TextField(blank=True)
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name="warehouse_controls", null=True, blank=True)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="warehouse_controls", null=True, blank=True)
    scope = models.CharField(max_length=40, default="TENANT")
    process = models.CharField(max_length=80, blank=True)
    settings = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_by_user_id = models.UUIDField(null=True, blank=True)
    updated_by_user_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "lattice_whscnt"


class StockKeepingUnit(TenantConfigurationModel):
    sku_code = models.CharField(max_length=80, unique=True)
    sku_type = models.CharField(max_length=40, default="PLACEHOLDER")
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "lattice_sku"


class OrderDefinition(TenantConfigurationModel):
    order_code = models.CharField(max_length=40, unique=True)
    order_type = models.CharField(max_length=40, default="CUSTOM")
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "lattice_order"


class InventoryMetadata(TenantConfigurationModel):
    inventory_code = models.CharField(max_length=40, unique=True)
    inventory_type = models.CharField(max_length=40, default="CUSTOM")
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "lattice_inv"


class WarehouseLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timestamp = models.DateTimeField(default=django_timezone.now)
    actor_user_id = models.UUIDField(null=True, blank=True)
    action = models.CharField(max_length=120)
    entity_type = models.CharField(max_length=80)
    entity_id = models.CharField(max_length=120, blank=True)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="warehouse_logs", null=True, blank=True)
    request_id = models.CharField(max_length=80, blank=True)
    result = models.CharField(max_length=24, default="SUCCESS")
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "lattice_log"
        ordering = ["-timestamp"]
