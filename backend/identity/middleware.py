from __future__ import annotations

from django.contrib.auth.models import AnonymousUser

from identity.jwt import JwtAuthenticationError, authenticate_token, get_request_token, jwt_error_response

SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
COOKIE_AUTH_UNSAFE_EXEMPT_PATHS = {
    "/api/v1/auth/token/refresh/",
    "/api/v1/auth/login/",
    "/api/v1/auth/mfa/verify/",
}
AUTH_BYPASS_PATHS = {
    "/api/v1/auth/login/",
    "/api/v1/auth/login/context/",
    "/api/v1/auth/token/refresh/",
    "/api/v1/auth/password/reset/request/",
    "/api/v1/auth/password/reset/confirm/",
}


class JwtAuthenticationMiddleware:
    """Authenticate JWTs early enough for session and tenant middleware."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path in AUTH_BYPASS_PATHS:
            return self.get_response(request)
        token, source = get_request_token(request)
        if token:
            if source == "cookie" and request.method not in SAFE_METHODS and request.path not in COOKIE_AUTH_UNSAFE_EXEMPT_PATHS:
                request.lattice_skip_cookie_jwt = True
                return self.get_response(request)
            try:
                principal = authenticate_token(token, token_type="access", source=source)
            except JwtAuthenticationError as exc:
                return jwt_error_response(exc.code, exc.message)
            request.user = principal.user
            request.lattice_jwt_principal = principal
            request.lattice_security_session = principal.session
        elif not hasattr(request, "user"):
            request.user = AnonymousUser()
        return self.get_response(request)
