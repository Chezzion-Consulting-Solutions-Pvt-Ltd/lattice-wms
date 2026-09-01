"""Health endpoints."""
from django.http import JsonResponse


def live(_request):
    return JsonResponse({"status": "ok"})


def ready(_request):
    return JsonResponse({"status": "ok"})
