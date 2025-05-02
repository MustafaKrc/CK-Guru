# worker/ml/services/factories/xai_strategy_factory.py
import logging
from typing import Any, Optional
import pandas as pd

from shared.schemas.enums import XAITypeEnum
from ..strategies.base_xai_strategy import BaseXAIStrategy
# Import concrete strategies
from ..strategies.shap_strategy import SHAPStrategy
from ..strategies.lime_strategy import LIMEStrategy
from ..strategies.feature_importance_strategy import FeatureImportanceStrategy
from ..strategies.decision_path_strategy import DecisionPathStrategy
from ..strategies.counterfactuals_strategy import CounterfactualsStrategy

logger = logging.getLogger(__name__)

class XAIStrategyFactory:
    """Factory to create XAI explanation strategy instances."""

    @staticmethod
    def create(
        xai_type: XAITypeEnum,
        model: Any,
        background_data: Optional[pd.DataFrame] = None
    ) -> BaseXAIStrategy:
        """
        Creates the appropriate XAI strategy based on the type.

        Args:
            xai_type: The enum member indicating the desired explanation type.
            model: The trained ML model object.
            background_data: Optional background dataset for certain methods (LIME).

        Returns:
            An instance of a BaseXAIStrategy subclass.

        Raises:
            ValueError: If the xai_type is unsupported.
        """
        logger.info(f"Creating XAI strategy for type: {xai_type.value}")
        if xai_type == XAITypeEnum.SHAP:
            return SHAPStrategy(model, background_data)
        elif xai_type == XAITypeEnum.LIME:
            if background_data is None:
                # LIME typically requires background data
                logger.warning("LIME strategy created without background data. May need fallback or error.")
            return LIMEStrategy(model, background_data)
        elif xai_type == XAITypeEnum.FEATURE_IMPORTANCE:
             # Feature importance might be derived from SHAP or model directly
             return FeatureImportanceStrategy(model, background_data) # Might need SHAP strategy internally?
        elif xai_type == XAITypeEnum.DECISION_PATH:
             # Check model compatibility within the strategy
             return DecisionPathStrategy(model)
        elif xai_type == XAITypeEnum.COUNTERFACTUALS:
             # Needs careful handling of background data and model wrapping
             return CounterfactualsStrategy(model, background_data)
        else:
            logger.error(f"Unsupported XAI type requested: {xai_type.value}")
            raise ValueError(f"Unsupported XAI type: {xai_type.value}")