from __future__ import annotations

import os
from abc import ABC, abstractmethod


class SecretProvider(ABC):
    @abstractmethod
    def get_secret(self, reference: str) -> str:
        """Return a secret by reference without logging or exposing it."""


class EnvironmentSecretProvider(SecretProvider):
    """Development-only secret provider.

    A reference such as `env:TENANT_ALPHA_DB_PASSWORD` resolves to that
    environment variable. Production should replace this provider with Vault,
    cloud Secret Manager, or equivalent.
    """

    def get_secret(self, reference: str) -> str:
        if not reference.startswith("env:"):
            raise ValueError("Unsupported development secret reference.")
        key = reference.removeprefix("env:")
        value = os.environ.get(key)
        if not value:
            raise ValueError("Configured secret reference is unavailable.")
        return value


def get_secret_provider() -> SecretProvider:
    return EnvironmentSecretProvider()
