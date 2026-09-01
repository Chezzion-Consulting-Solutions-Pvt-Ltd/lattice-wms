from django.urls import path

from identity.views import (
    LoginView,
    LoginContextView,
    LogoutView,
    MeView,
    MfaDisableView,
    MfaSetupView,
    MfaVerifyView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RecoveryCodeRegenerateView,
    RevokeOtherSessionsView,
    RevokeSessionView,
    SessionListView,
)

urlpatterns = [
    path("login/context/", LoginContextView.as_view(), name="login-context"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("password/reset/request/", PasswordResetRequestView.as_view(), name="password-reset-request"),
    path("password/reset/confirm/", PasswordResetConfirmView.as_view(), name="password-reset-confirm"),
    path("me/", MeView.as_view(), name="me"),
    path("sessions/", SessionListView.as_view(), name="sessions"),
    path("sessions/<uuid:session_id>/", RevokeSessionView.as_view(), name="session-revoke"),
    path("sessions/revoke-others/", RevokeOtherSessionsView.as_view(), name="session-revoke-others"),
    path("mfa/setup/", MfaSetupView.as_view(), name="mfa-setup"),
    path("mfa/verify/", MfaVerifyView.as_view(), name="mfa-verify"),
    path("mfa/disable/", MfaDisableView.as_view(), name="mfa-disable"),
    path("mfa/recovery/regenerate/", RecoveryCodeRegenerateView.as_view(), name="mfa-recovery-regenerate"),
]
