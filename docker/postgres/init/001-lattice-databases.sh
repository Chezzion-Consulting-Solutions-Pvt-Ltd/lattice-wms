#!/usr/bin/env bash
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
DO
\$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${POSTGRES_APP_USER}') THEN
    CREATE ROLE ${POSTGRES_APP_USER} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD '${POSTGRES_APP_PASSWORD}';
  END IF;
END
\$\$;

GRANT CONNECT, TEMPORARY ON DATABASE ${POSTGRES_DB} TO ${POSTGRES_APP_USER};
GRANT USAGE, CREATE ON SCHEMA public TO ${POSTGRES_APP_USER};

DO
\$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'lattice_alpha_app') THEN
    CREATE ROLE lattice_alpha_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT PASSWORD '${TENANT_ALPHA_DB_PASSWORD}';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'lattice_beta_app') THEN
    CREATE ROLE lattice_beta_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT PASSWORD '${TENANT_BETA_DB_PASSWORD}';
  END IF;
END
\$\$;
SQL

createdb --username "$POSTGRES_USER" --owner lattice_alpha_app lattice_alpha || true
createdb --username "$POSTGRES_USER" --owner lattice_beta_app lattice_beta || true
createdb --username "$POSTGRES_USER" --owner "$POSTGRES_APP_USER" test_lattice_control || true

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname lattice_alpha <<SQL
REVOKE ALL ON DATABASE lattice_alpha FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE lattice_alpha TO lattice_alpha_app;
GRANT USAGE, CREATE ON SCHEMA public TO lattice_alpha_app;
SQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname lattice_beta <<SQL
REVOKE ALL ON DATABASE lattice_beta FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE lattice_beta TO lattice_beta_app;
GRANT USAGE, CREATE ON SCHEMA public TO lattice_beta_app;
SQL
