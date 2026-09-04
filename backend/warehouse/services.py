from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from django.db import transaction

from tenancy.context import get_tenant_context
from warehouse.models import Bay, SequenceNumber, StorageSection, StorageType, Warehouse, Zone


BAY_PATTERN_TOKENS = {"aisle", "rack", "level", "position"}
MAX_BAY_BATCH_SIZE = 500


@dataclass(frozen=True)
class BayDraft:
    warehouse_id: str
    zone_id: str
    storage_type_id: str | None
    section_id: str | None
    bin_code: str
    barcode: str
    aisle: str
    rack: str
    level: str
    position: str
    bay_type: str

    def as_payload(self) -> dict[str, Any]:
        return {
            "warehouse_id": self.warehouse_id,
            "zone_id": self.zone_id,
            "storage_type_id": self.storage_type_id,
            "section_id": self.section_id,
            "bay_code": self.bin_code,
            "bin_code": self.bin_code,
            "barcode": self.barcode,
            "aisle": self.aisle,
            "rack": self.rack,
            "level": self.level,
            "position": self.position,
            "bay_type": self.bay_type,
        }


class BayBulkCreationService:
    def preview(self, payload: dict[str, Any]) -> dict[str, Any]:
        drafts = self._drafts(payload)
        codes = [draft.bin_code for draft in drafts]
        duplicate_codes = sorted({code for code in codes if codes.count(code) > 1})
        existing_codes = set(Bay.objects.filter(warehouse_id=payload.get("warehouse_id"), bin_code__in=codes).values_list("bin_code", flat=True))
        failures = []
        if len(drafts) > MAX_BAY_BATCH_SIZE:
            failures.append(f"Batch size cannot exceed {MAX_BAY_BATCH_SIZE}.")
        if duplicate_codes:
            failures.append("Generated bay codes contain duplicates.")
        if existing_codes:
            failures.append("Generated bay codes already exist.")
        return {
            "count": len(drafts),
            "sample": [draft.as_payload() for draft in drafts[:25]],
            "duplicates": duplicate_codes,
            "existing": sorted(existing_codes),
            "validation_failures": failures,
        }

    def commit(self, payload: dict[str, Any]) -> dict[str, Any]:
        preview = self.preview(payload)
        if preview["validation_failures"]:
            return {**preview, "created": 0}
        drafts = self._drafts(payload)
        with transaction.atomic(using=get_tenant_context().database_alias):
            bays = [
                Bay(
                    warehouse_id=draft.warehouse_id,
                    zone_id=draft.zone_id,
                    storage_type_id=draft.storage_type_id,
                    section_id=draft.section_id,
                    bin_code=draft.bin_code,
                    barcode=draft.barcode,
                    aisle=draft.aisle,
                    rack=draft.rack,
                    level=draft.level,
                    position=draft.position,
                    bay_type=draft.bay_type,
                )
                for draft in drafts
            ]
            Bay.objects.bulk_create(bays)
        return {**preview, "created": len(drafts)}

    def _drafts(self, payload: dict[str, Any]) -> list[BayDraft]:
        warehouse = Warehouse.objects.get(id=payload["warehouse_id"])
        zone = Zone.objects.get(id=payload["zone_id"], warehouse=warehouse)
        storage_type_id = payload.get("storage_type_id") or None
        section_id = payload.get("section_id") or None
        if storage_type_id:
            StorageType.objects.get(id=storage_type_id, warehouse=warehouse)
        if section_id:
            StorageSection.objects.get(id=section_id, warehouse=warehouse, zone=zone)
        pattern = str(payload.get("pattern") or "{aisle}-{rack}-{level}-{position}")
        unknown_tokens = set(re.findall(r"{([^{}]+)}", pattern)) - BAY_PATTERN_TOKENS
        if unknown_tokens:
            raise ValueError(f"Unsupported bay pattern token: {', '.join(sorted(unknown_tokens))}")
        rows = []
        for aisle in _range_values(payload.get("aisles") or payload.get("aisle_range") or ["A"]):
            for rack in _range_values(payload.get("racks") or payload.get("rack_range") or ["01"]):
                for level in _range_values(payload.get("levels") or payload.get("level_range") or ["01"]):
                    for position in _range_values(payload.get("positions") or payload.get("position_range") or ["01"]):
                        code = pattern.format(aisle=aisle, rack=rack, level=level, position=position)
                        rows.append(
                            BayDraft(
                                warehouse_id=str(warehouse.id),
                                zone_id=str(zone.id),
                                storage_type_id=str(storage_type_id) if storage_type_id else None,
                                section_id=str(section_id) if section_id else None,
                                bin_code=code,
                                barcode=str(payload.get("barcode_prefix") or "") + code,
                                aisle=aisle,
                                rack=rack,
                                level=level,
                                position=position,
                                bay_type=str(payload.get("bay_type") or ""),
                            )
                        )
        return rows


class SequenceService:
    def preview(self, sequence: SequenceNumber) -> str:
        return self._format(sequence, sequence.current_value + 1)

    def reserve(self, sequence_id: str) -> str:
        with transaction.atomic(using=get_tenant_context().database_alias):
            sequence = SequenceNumber.objects.select_for_update().get(id=sequence_id)
            next_value = sequence.current_value + 1
            if sequence.max_value is not None and next_value > sequence.max_value:
                raise ValueError("Sequence maximum value exceeded.")
            sequence.current_value = next_value
            sequence.save(update_fields=["current_value", "updated_at"])
            return self._format(sequence, next_value)

    def reset(self, sequence_id: str) -> str:
        with transaction.atomic(using=get_tenant_context().database_alias):
            sequence = SequenceNumber.objects.select_for_update().get(id=sequence_id)
            sequence.current_value = max(sequence.min_value - 1, 0)
            sequence.save(update_fields=["current_value", "updated_at"])
            return self.preview(sequence)

    def _format(self, sequence: SequenceNumber, value: int) -> str:
        number = str(value).zfill(sequence.padding)
        return f"{sequence.prefix}{number}{sequence.suffix}"


def _range_values(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if isinstance(value, dict):
        start = str(value.get("start") or value.get("from") or "")
        end = str(value.get("end") or value.get("to") or start)
        width = int(value.get("width") or max(len(start), len(end), 1))
        return _inclusive_range(start, end, width)
    text = str(value)
    if ".." in text:
        start, end = text.split("..", 1)
        return _inclusive_range(start, end, max(len(start), len(end), 1))
    return [part.strip() for part in text.split(",") if part.strip()]


def _inclusive_range(start: str, end: str, width: int) -> list[str]:
    if start.isdigit() and end.isdigit():
        return [str(value).zfill(width) for value in range(int(start), int(end) + 1)]
    if len(start) == 1 and len(end) == 1 and start.isalpha() and end.isalpha():
        first, last = ord(start.upper()), ord(end.upper())
        return [chr(value) for value in range(first, last + 1)]
    return [start]
