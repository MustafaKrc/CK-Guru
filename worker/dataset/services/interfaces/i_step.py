# worker/dataset/services/interfaces/i_step.py
from abc import ABC, abstractmethod
from typing import Any

from services.context import DatasetContext  # Forward reference ok with '..'


class IDatasetGeneratorStep(ABC):
    """Abstract base class for a step in the dataset generation pipeline."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Returns the user-friendly name of the step."""
        pass

    @abstractmethod
    async def execute(self, context: "DatasetContext", **kwargs: Any) -> "DatasetContext":
        """
        Executes the logic for this step.

        Args:
            context: The shared DatasetContext object.
            **kwargs: Injected dependencies (e.g., repositories, services).

        Returns:
            The updated DatasetContext object.

        Raises:
            Exception: If a critical error occurs that should stop the pipeline.
        """
        pass
