# worker/ml/services/strategies/base_xai_strategy.py
import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class BaseXAIStrategy(ABC):
    """Abstract Base Class for different XAI explanation generation methods."""

    def __init__(self, model: Any, background_data: Optional[pd.DataFrame] = None):
        self.model = model
        self.background_data = background_data
        logger.debug(f"Initialized XAI Strategy: {self.__class__.__name__}")

    @abstractmethod
    def explain(
        self, X_inference: pd.DataFrame, identifiers_df: pd.DataFrame
    ) -> Optional[Any]:
        """
        Generates the explanation for the given inference instances.

        Args:
            X_inference: DataFrame containing the feature vectors for which
                            explanations are needed. Columns must match model expectations.
            identifiers_df: DataFrame containing identifying info (like file, class)
                            aligned row-wise with X_inference.

        Returns:
            A Pydantic model instance containing the structured explanation results
            (e.g., SHAPResultData, LIMEResultData) or None if explanation fails.
        """
        pass
