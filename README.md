# Lattice

Lattice is an enterprise-grade SaaS Warehouse Management System being built with database-per-client tenant isolation.

## Current Milestone

The repository is initialized for the Lattice Secure Core:

- Django + DRF backend
- React + TypeScript frontend
- PostgreSQL control database
- Dedicated local Alpha/Beta tenant databases and roles
- Redis and Celery
- Tenant context, resolver, router, provisioning abstractions
- Security architecture documentation and ADRs
- Initial tenant isolation tests

Authentication, MFA, RBAC, and WMS operational modules are intentionally next steps after the tenant database foundation is verified.

## Local Start

```bash
cp .env.example .env
docker compose up --build
```

In another terminal:

```bash
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py seed_local_tenants
docker compose exec backend pytest
```

Frontend: `http://localhost:5173`

Backend health: `http://localhost:8000/health/live`

## Tenant Provisioning Dry Run

```bash
docker compose exec backend python manage.py provision_tenant_db alpha --secret-reference env:TENANT_ALPHA_DB_PASSWORD
docker compose exec backend python manage.py provision_tenant_db beta --secret-reference env:TENANT_BETA_DB_PASSWORD
```

Production tenant provisioning must use separated administrative credentials and a real secret manager.

## Database Credential Isolation Acceptance Test

After `docker compose up --build`, run:

```bash
docker compose exec backend env LATTICE_RUN_DB_ISOLATION=1 pytest tenancy/tests/test_acceptance_db_isolation.py
```

This proves `lattice_alpha_app` can connect to `lattice_alpha` and is rejected by PostgreSQL when attempting `lattice_beta`.

## Local Non-Docker Checks

```powershell
python -m venv .venv
```

From `backend/`:

```powershell
& '..\.venv\Scripts\python.exe' -m pip install --disable-pip-version-check -r requirements.txt
& '..\.venv\Scripts\python.exe' manage.py check
$env:DJANGO_SECRET_KEY='local-deploy-check-secret-with-more-than-fifty-characters-123456789'
& '..\.venv\Scripts\python.exe' manage.py check --deploy
& '..\.venv\Scripts\python.exe' -m pytest tenancy\tests\test_context.py tenancy\tests\test_router.py tenancy\tests\test_provisioning.py tenancy\tests\test_celery_context.py
```
