# Lattice Deployment

Production deployment must place PostgreSQL and Redis on private networks, expose Django only through a gateway/load balancer, use HTTPS, and fetch secrets from a managed secret backend.

Run `python manage.py check --deploy` in CI with production-like settings before deployment.
