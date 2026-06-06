"""Domain-level exceptions for the PruebaTecnica application.

All custom exceptions inherit from DomainError so callers can catch
the entire domain exception hierarchy with a single except clause.
"""


class DomainError(Exception):
    """Base class for all domain exceptions."""


class AuthenticationError(DomainError):
    """Raised when user credentials are invalid or the user is inactive."""


class TokenExpiredError(DomainError):
    """Raised when a JWT has passed its expiration time."""


class InvalidTokenError(DomainError):
    """Raised when a JWT signature, structure, or claims are invalid."""


class NotFoundError(DomainError):
    """Raised when a requested resource does not exist."""


class ValidationError(DomainError):
    """Raised when input data fails domain validation rules."""


class PermissionDeniedError(DomainError):
    """Raised when the requesting user lacks the required role or permission."""


class StorageError(DomainError):
    """Raised when an S3 or file-storage operation fails."""


class AIServiceError(DomainError):
    """Raised when an AI classification or extraction call fails."""
