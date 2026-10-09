"""Backward compatibility re-exports for RuntimeGateway."""

from agent_security.runtime.gateway import (
    AuthenticatedAgent,
    StoredAction,
    RuntimeGateway,
)

__all__ = [
    "AuthenticatedAgent",
    "StoredAction",
    "RuntimeGateway",
]
