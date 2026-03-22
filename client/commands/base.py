from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseCommand(ABC):
    """Abstract base class for all client commands."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the command name."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Return the command description."""
        pass

    @abstractmethod
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the command and return the result."""
        pass
