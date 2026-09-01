# Lattice Audit

Audit logging is a core product feature. Sensitive operations record request ID, tenant ID, user IDs, source metadata, action, resource type, result, and safe before/after summaries.

Audit logs must not contain passwords, authentication tokens, MFA secrets, recovery codes, database credentials, API keys, or raw connection strings.

Current security events include:

- `LOGIN_SUCCESS`
- `LOGIN_FAILED`
- `LOGIN_THROTTLED`
- `SUSPICIOUS_LOGIN`
- `LOGOUT`
- `SESSION_REVOKED`
- `PASSWORD_RESET_REQUESTED`
- `PASSWORD_RESET_COMPLETED`
- `PASSWORD_RESET_FAILED`
- `MFA_SETUP_STARTED`
- `MFA_VERIFIED`
- `MFA_VERIFY_FAILED`
- `MFA_DISABLED`
- `MFA_RECOVERY_REGENERATED`
