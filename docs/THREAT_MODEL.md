# Lattice Threat Model

## Assets

- Tenant WMS data
- Control-plane tenant metadata
- Global user identity records
- Tenant database credentials and secret references
- Audit logs
- Redis queues and Celery task payloads
- Object storage files
- Backups and PITR artifacts
- CI/CD credentials and deployment artifacts

## Trust Boundaries

- Internet to gateway
- Gateway to Django
- Django to control database
- Django to tenant databases
- Django/Celery to Redis
- Django/Celery to object storage
- CI/CD to runtime infrastructure
- Administrative access to production networks and databases

## Major Threats

| Threat | Attack Path | Impact | Mitigation | Detection | Test |
| --- | --- | --- | --- | --- | --- |
| Cross-tenant database access | User forges tenant or DB selector | Tenant data breach | Server-side resolver, membership checks, DB router fail-closed, separate DB roles | Audit denied tenant resolution events | Cross-tenant object and forged header tests |
| Tenant context leakage | Context persists between requests or Celery tasks | Wrong tenant data exposure | `ContextVar`, context managers, `finally` cleanup | Structured logs with request/tenant IDs | Context leakage tests |
| Credential disclosure | Secret appears in logs/errors/docs | Infrastructure compromise | Secret references only, redaction filters, safe errors | Secret scanning and log tests | Secrets logging tests |
| BOLA | ID changed to unauthorized object | Data disclosure or modification | Object-level authorization and warehouse scope | Audit denied object access | Object enumeration tests |
| Suspended tenant access | Status not checked after auth | Contract/security policy bypass | Tenant status checks in resolver/middleware | Audit tenant unavailable events | Suspended tenant test |
| Abuse of login endpoints | Credential stuffing or brute force | Account compromise | DRF throttles, IP/user policies, audit events | Auth event monitoring | Login abuse tests |
| Inventory race | Concurrent allocation/pick | Negative or inaccurate stock | Transactions, row locks, ledger invariants | Inventory conflict events | Inventory race test |
| Duplicate GR/PGI | Retry repeats state change | Duplicate receipt or deduction | Idempotency keys and business constraints | Duplicate command audit | Duplicate GR/PGI tests |
| CI/CD compromise | Secrets or vulnerable images shipped | Platform compromise | Secret scan, SAST, dependency scan, image scan, approvals | CI audit logs | Pipeline gates |
| Backup exposure | Backup copied or restored to wrong boundary | Tenant data disclosure | Tenant-specific backup metadata, encryption, access controls | Backup access logs | DR restore drills |
