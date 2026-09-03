from __future__ import annotations

from django.http import JsonResponse
from rest_framework.views import APIView

from audit.models import AuditEvent
from control.api.common import IsOwnerConsoleUser
from control.api.serializers import audit_summary


class OwnerSecurityEventsView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]

    def get(self, request):
        events = apply_event_filters(AuditEvent.objects.filter(result__in=[AuditEvent.Result.DENIED, AuditEvent.Result.FAILURE]), request).order_by("-timestamp")[:100]
        return JsonResponse({"events": [audit_summary(event) for event in events]})


class OwnerAuditLogsView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]

    def get(self, request):
        events = apply_event_filters(AuditEvent.objects.all(), request).order_by("-timestamp")[:100]
        return JsonResponse({"audit_logs": [audit_summary(event) for event in events]})


def apply_event_filters(queryset, request):
    action = request.GET.get("action")
    result = request.GET.get("result")
    request_id = request.GET.get("request_id")
    resource_type = request.GET.get("resource_type")
    resource_id = request.GET.get("resource_id")
    if action:
        queryset = queryset.filter(action__icontains=action)
    if result:
        queryset = queryset.filter(result=result)
    if request_id:
        queryset = queryset.filter(request_id=request_id)
    if resource_type:
        queryset = queryset.filter(resource_type__icontains=resource_type)
    if resource_id:
        queryset = queryset.filter(resource_id=resource_id)
    return queryset
