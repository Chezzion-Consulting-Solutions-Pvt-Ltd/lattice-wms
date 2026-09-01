"""ASGI config for Lattice."""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lattice.settings")

application = get_asgi_application()
