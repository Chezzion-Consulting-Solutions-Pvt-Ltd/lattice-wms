# Security Measures Assessment

Assessment date: 2026-09-01

This assessment checks the current Lattice application against the requested security evidence categories. It distinguishes product controls implemented in the app from external assurance artifacts that must be obtained from vendors, auditors, or independent assessors.

## Summary

| Area | Current status | Notes |
| --- | --- | --- |
| Security Assessment Checklist | READY TO REQUEST | Vendor evidence request document exists; attached spreadsheet must still be completed by each vendor. |
| SOC 2 Type II Report | NOT AVAILABLE IN APP | Must be obtained from the vendor/auditor. A bridge letter is required if the report period is not current. |
| Data Privacy And Protection Compliance | PARTIAL | Region metadata and security architecture exist; formal privacy compliance evidence is external/policy work. |
| ISO Certification And SoA | NOT AVAILABLE IN APP | ISO certificates and Statement of Applicability must be obtained from the certified organization. |
| Vulnerability Assessment Reports | NOT AVAILABLE | CI scaffolding exists, but independent VA reports and closure evidence are not present. |
| Web Application Penetration Test | NOT AVAILABLE | Requires independent testing report. |
| LLM Security Assessment | NOT APPLICABLE CURRENTLY | No LLM feature is implemented in the application. Reassess if AI/LLM functionality is added. |
| Mobile Application Penetration Test | NOT APPLICABLE CURRENTLY | No iOS or Android app is implemented in this repository. Reassess when mobile apps are added. |
| DR Drill Report | NOT AVAILABLE | Backup/DR design docs exist, but drill execution evidence is not present. |
| Backup Restoration Test Report | NOT AVAILABLE | Backup restoration test evidence is not present. |

## Implemented And Verified Application Controls

- Database-per-tenant isolation is implemented and verified.
- Each tenant has independent PostgreSQL database metadata and runtime role metadata.
- Tenant database routing is server-side and fails closed.
- Browser-supplied database names, aliases, headers, and query selectors are rejected.
- Missing tenant context fails closed.
- Missing tenant database mapping fails closed.
- Suspended tenants are denied.
- Reciprocal Alpha/Beta PostgreSQL credential denial is tested.
- Celery tenant context isolation is tested.
- Owner Console uses control-plane data for normal platform administration.
- Tenant database credentials are stored as secret references, not plaintext columns.
- Owner database configuration rejects raw passwords and connection strings.
- API responses and audit summaries avoid exposing tenant database secret reference values.
- Login, logout, current-user, session tracking, session revocation, MFA, password reset, and login abuse protections are implemented and tested.
- Security headers, CSRF middleware, session cookies, HSTS production settings, frame protection, content type protections, referrer policy, and CSP configuration are present.
- Docker Compose keeps PostgreSQL and Redis private to the Compose network while exposing only frontend/backend service ports.

## Partial Or Incomplete Application Controls

- RBAC and granular permissions exist at model/helper level, but complete platform administration UI is still in progress.
- Warehouse scope checks exist at model/helper level, but tenant administration pages are still in progress.
- Audit logging exists for key identity and owner tenant operations, but full audit browsing and complete sensitive operation coverage are still in progress.
- CI exists for build/check/test, but full automated SAST, dependency audit, container scan, secret scan, and DAST gates are not implemented.
- Backup metadata, restore workflows, PITR automation, and DR execution evidence are not implemented.
- Data retention, deletion workflows, privacy rights workflows, subprocessors, and formal data processing documentation are not implemented in-app.

## Latest Validation

- Docker backend security/test suite with `LATTICE_RUN_DB_ISOLATION=1`: 52 passed.
- Frontend build: passed.
- Frontend lint: passed.
- Django system check: passed.

## Evidence Documents

- `docs/SECURITY_CHECKLIST.md`
- `docs/SECURITY_ARCHITECTURE.md`
- `docs/THREAT_MODEL.md`
- `docs/TENANCY.md`
- `docs/AUTHENTICATION.md`
- `docs/AUTHORIZATION.md`
- `docs/AUDIT.md`
- `docs/BACKUP_DR.md`
- `docs/VENDOR_SECURITY_EVIDENCE_REQUEST.md`

## Required Next Security Work

1. Send `docs/VENDOR_SECURITY_EVIDENCE_REQUEST.md` and the attached Security Assessment Checklist spreadsheet to each vendor.
2. Collect SOC 2 Type II reports or bridge letters.
3. Collect ISO certificates and Statement of Applicability where applicable.
4. Schedule independent web application and infrastructure VA/PT.
5. Add automated SAST, dependency, secret, and container image scanning to CI.
6. Build backup metadata, restore validation, and DR drill evidence processes.
7. Complete platform IAM, RBAC administration, audit browsing, and tenant administration authorization coverage.
