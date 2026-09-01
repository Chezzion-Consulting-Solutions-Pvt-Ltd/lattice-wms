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

    def __str__(self) -> str:
        return self.plant_code


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

    @property
    def warehouse_code(self) -> str:
        return self.code


class WarehouseScopedObject(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    external_reference = models.CharField(max_length=120, blank=True)

    class Meta:
        abstract = True


class WarehouseProbeObject(WarehouseScopedObject):
    """Minimal tenant object used by isolation tests before WMS modules exist."""

    pass


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

    class Meta:
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

    class Meta:
        constraints = [models.UniqueConstraint(fields=["warehouse", "storage_type_code"], name="unique_storage_type_code_per_warehouse")]


class StorageSection(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="sections")
    zone = models.ForeignKey(Zone, on_delete=models.PROTECT, related_name="sections")
    storage_type = models.ForeignKey(StorageType, on_delete=models.PROTECT, related_name="sections")
    section_code = models.CharField(max_length=40)
    name = models.CharField(max_length=160)
    status = models.CharField(max_length=24, choices=LifecycleStatus.choices, default=LifecycleStatus.ACTIVE)
    sequence = models.PositiveIntegerField(default=0)
    description = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["warehouse", "section_code"], name="unique_section_code_per_warehouse")]

    def clean(self):
        if self.zone_id and self.zone.warehouse_id != self.warehouse_id:
            raise ValidationError({"zone": "Zone must belong to the selected warehouse."})
        if self.storage_type_id and self.storage_type.warehouse_id != self.warehouse_id:
            raise ValidationError({"storage_type": "Storage type must belong to the selected warehouse."})


class Bin(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="bins")
    zone = models.ForeignKey(Zone, on_delete=models.PROTECT, related_name="bins")
    storage_type = models.ForeignKey(StorageType, on_delete=models.PROTECT, related_name="bins")
    section = models.ForeignKey(StorageSection, on_delete=models.PROTECT, related_name="bins", null=True, blank=True)
    bin_code = models.CharField(max_length=80)
    barcode = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=24, choices=LifecycleStatus.choices, default=LifecycleStatus.ACTIVE)
    aisle = models.CharField(max_length=40, blank=True)
    bay = models.CharField(max_length=40, blank=True)
    level = models.CharField(max_length=40, blank=True)
    position = models.CharField(max_length=40, blank=True)
    max_weight = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    max_volume = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    max_hu_count = models.PositiveIntegerField(null=True, blank=True)
    is_pickable = models.BooleanField(default=True)
    is_putaway_allowed = models.BooleanField(default=True)
    is_blocked = models.BooleanField(default=False)
    is_countable = models.BooleanField(default=True)

    class Meta:
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
