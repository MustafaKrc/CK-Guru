# worker/ml/services/strategies/base_decision_path_strategy.py
import logging
from abc import abstractmethod
from typing import Any, Optional  # Keep Any for model

import pandas as pd

from shared.schemas.xai import (  # Import the Pydantic model for results
    DecisionPathResultData,
)

from .base_xai_strategy import BaseXAIStrategy

logger = logging.getLogger(__name__)


class BaseDecisionPathStrategy(BaseXAIStrategy):
    """
    Abstract Base Class for strategies that generate decision path explanations.
    """

    def __init__(self, model: Any, background_data: Optional[pd.DataFrame] = None):
        # Decision path strategies usually don't need background_data,
        # but keep for consistency with BaseXAIStrategy if some variant might.
        super().__init__(model, background_data)
        logger.debug(f"Initialized BaseDecisionPathStrategy: {self.__class__.__name__}")

    @abstractmethod
    def explain(
        self, X_inference: pd.DataFrame, identifiers_df: pd.DataFrame
    ) -> Optional[DecisionPathResultData]:
        """
        Generates the decision path explanation for the given inference instances.

        Args:
            X_inference: DataFrame containing the feature vectors.
            identifiers_df: DataFrame containing identifying info.

        Returns:
            A DecisionPathResultData object containing the structured path results,
            or None if explanation fails or is not applicable.
        """
        pass
