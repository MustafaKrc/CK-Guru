# shared/exceptions.py
import traceback
from celery import states

class NotFoundError(Exception):
    """Raised when a requested resource is not found."""

class ConflictError(Exception):
    """Raised when an operation conflicts with the current state."""

class InternalError(Exception):
    """Raised for internal processing errors."""


def build_failure_meta(exc: Exception, extra: dict | None = None) -> dict:
    meta = {
        "exc_type":   type(exc).__name__,
        "exc_message": str(exc),
        "exc_module":  exc.__class__.__module__,
        "traceback":   traceback.format_exc(),
    }
    if extra:
        meta.update(extra)
    return meta

