"""Homebase module base class.

Every module implements ModuleBase and provides a create_module() factory.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class ToolDefinition:
    """A single MCP tool exposed by a module."""
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable


class ModuleBase(ABC):
    """Base class for all Homebase modules."""

    def __init__(self, config: dict[str, Any]):
        self.config = config

    def check_dependencies(self) -> tuple[bool, list[str]]:
        """Check if required packages are importable. Override to declare deps."""
        missing = []
        for pkg in self.required_packages:
            try:
                __import__(pkg)
            except ImportError:
                missing.append(pkg)
        return len(missing) == 0, missing

    @property
    def required_packages(self) -> list[str]:
        """Packages that must be importable. Override in subclass."""
        return []

    @abstractmethod
    def get_tools(self) -> list[ToolDefinition]:
        """Return all tools this module provides."""
        ...
