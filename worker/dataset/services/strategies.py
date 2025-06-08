# worker/dataset/services/strategies.py
import logging
from abc import ABC, abstractmethod
from typing import List, Type

# Import step interface and concrete step classes
from services.interfaces import IDatasetGeneratorStep
from services.steps import (
    LoadConfigurationStep,
    ProcessGloballyStep,
    SelectFinalColumnsStep,
    FeatureSelectionStep,
    StreamAndProcessBatchesStep,
    ApplyBotPatternsStep,
    WriteOutputStep,
)

logger = logging.getLogger(__name__)


class IDatasetGenerationStrategy(ABC):
    """Abstract base class for defining a dataset generation pipeline strategy."""

    @abstractmethod
    def get_steps(self) -> List[Type[IDatasetGeneratorStep]]:
        """Returns the ordered list of step types for this strategy."""
        pass


class DefaultDatasetGenerationStrategy(IDatasetGenerationStrategy):
    """
    Standard strategy for generating a dataset:
    Load -> Process Batches -> Process Globally -> Select Columns -> Write Output
    """

    def get_steps(self) -> List[Type[IDatasetGeneratorStep]]:
        logger.debug("Using DefaultDatasetGenerationStrategy")
        return [
            LoadConfigurationStep,
            StreamAndProcessBatchesStep,  # This step orchestrates batch sub-steps
            ProcessGloballyStep,  # This step orchestrates global sub-steps
            SelectFinalColumnsStep,
            ApplyBotPatternsStep, 
            FeatureSelectionStep,
            WriteOutputStep,
        ]


# Add other strategies here if needed in the future
# class AlternativeDatasetGenerationStrategy(IDatasetGenerationStrategy):
#     def get_steps(self) -> List[Type[IDatasetGeneratorStep]]:
#         # Define a different sequence of steps
#         pass
