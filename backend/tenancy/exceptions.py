class LatticeSecurityError(Exception):
    """Base exception for controlled Lattice security failures."""


class TenantContextError(LatticeSecurityError):
    """Raised when tenant data is accessed without trusted tenant context."""


class TenantResolutionError(LatticeSecurityError):
    """Raised when a request cannot be mapped to an authorized tenant."""


class TenantUnavailableError(LatticeSecurityError):
    """Raised when a tenant is suspended, unavailable, or not provisioned."""


class WarehouseAuthorizationError(LatticeSecurityError):
    """Raised when a user is not authorized for a warehouse."""


class AuthorizationError(LatticeSecurityError):
    """Raised when authorization fails."""


class BusinessRuleViolation(Exception):
    """Raised when business input violates domain rules."""


class InventoryConflict(BusinessRuleViolation):
    """Raised when inventory concurrency rules reject an operation."""


class InvalidStateTransition(BusinessRuleViolation):
    """Raised when a workflow transition is invalid."""
