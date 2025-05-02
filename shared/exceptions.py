class NotFoundError(Exception):
    """Raised when a requested resource is not found."""

class ConflictError(Exception):
    """Raised when an operation conflicts with the current state."""

class InternalError(Exception):
    """Raised for internal processing errors."""
