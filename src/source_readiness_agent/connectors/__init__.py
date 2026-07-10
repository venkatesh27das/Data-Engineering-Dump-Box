"""Read-only source connectors."""

from .base import SourceConnector
from .mock import MockConnector

__all__ = ["SourceConnector", "MockConnector"]
