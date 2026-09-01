from __future__ import annotations

import uuid

from django.db import models


class AuditEvent(models.Model):
    class Result(models.TextChoices):
        SUCCESS = "SUCCESS", "Success"
        DENIED = "DENIED", "Denied"
        FAILURE = "FAILURE", "Failure"

    event_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    request_id = models.CharField(max_length=80, db_index=True)
    tenant_id = models.UUIDField(null=True, blank=True, db_index=True)
    global_user_id = models.UUIDField(null=True, blank=True, db_index=True)
    tenant_user_id = models.UUIDField(null=True, blank=True)
    warehouse_id = models.UUIDField(null=True, blank=True)
    device_id = models.CharField(max_length=120, blank=True)
    source_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    action = models.CharField(max_length=120)
    resource_type = models.CharField(max_length=120, blank=True)
    resource_id = models.CharField(max_length=120, blank=True)
    before_summary = models.JSONField(default=dict, blank=True)
    after_summary = models.JSONField(default=dict, blank=True)
    result = models.CharField(max_length=24, choices=Result.choices)
    failure_reason = models.CharField(max_length=240, blank=True)
    correlation_id = models.CharField(max_length=80, blank=True, db_index=True)

    class Meta:
        ordering = ["-timestamp"]
