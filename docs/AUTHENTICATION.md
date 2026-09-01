# Lattice Authentication

Authentication is part of the Owner Console + Platform IAM milestone. Lattice uses Django's authentication framework with the control-plane `GlobalUser` model as the custom user model.

Browser authentication should use secure HttpOnly cookie/session mechanisms where practical. Sensitive tokens must not be stored in `localStorage`.

Implemented foundation:

- Email/password login through Django password hashers with Argon2 configured first.
- Logout with tracked security-session revocation.
- Current-user and active-session APIs.
- Disabled-account checks and security audit events for login/logout/session revocation.
- TOTP MFA setup and verification.
- Recovery-code regeneration with one-way hashed recovery codes and single-use verification.
- Password reset request/confirm endpoints:
  - `POST /api/v1/auth/password/reset/request/`
  - `POST /api/v1/auth/password/reset/confirm/`
- Generic password-reset request responses to prevent user enumeration.
- Cryptographically random reset tokens stored only as hashes with expiry and one-time use.
- Password reset revokes active tracked sessions for the user.
- Per-IP login throttling, per-user failed-login counters, configurable temporary lockout, and recovery after lockout.
- API security-session enforcement for revoked and expired tracked sessions.
- New MFA device secrets are stored in a keyed encrypted envelope using `MFA_SECRET_ENCRYPTION_KEY`.

Pending before completion:

- Complete platform IAM administration APIs and Owner Console screens.
- Production secret-manager/KMS sourcing for `MFA_SECRET_ENCRYPTION_KEY`.
