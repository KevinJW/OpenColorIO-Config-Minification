"""Base protocol definition for minification transformations."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class Transform(Protocol):
    """Protocol defining a single minification transformation step."""

    name: str
    description: str
    is_lossy: bool

    def apply(self, content: str) -> str:
        """Apply transformation to OCIO configuration text and return modified text."""
        ...
