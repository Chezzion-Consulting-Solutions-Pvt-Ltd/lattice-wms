from rest_framework.response import Response
from rest_framework.views import APIView

from tenancy.context import get_tenant_context


class TenantProbeView(APIView):
    throttle_scope = "standard_api"

    def get(self, request):
        context = get_tenant_context()
        return Response(
            {
                "tenant_code": context.tenant_code,
                "request_id": getattr(request, "request_id", ""),
            }
        )
