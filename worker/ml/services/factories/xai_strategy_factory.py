# worker/ml/services/factories/xai_strategy_factory.py
import logging
from typing import Any, List, Optional  # Added List

import pandas as pd

# Model types from sklearn
# from sklearn.svm import SVC # Not directly used by factory logic here
# Import ModelTypeEnum from shared schemas
from shared.schemas.enums import ModelTypeEnum, XAITypeEnum

from ..strategies.base_xai_strategy import BaseXAIStrategy
from ..strategies.counterfactuals_strategy import CounterfactualsStrategy

# Feature Importance Strategies
from ..strategies.feature_importance_strategy import FeatureImportanceStrategy
from ..strategies.lightgbm_decision_path_strategy import LightGBMDecisionPathStrategy
from ..strategies.lime_strategy import LIMEStrategy
from ..strategies.shap_strategy import SHAPStrategy

# Decision Path Strategies
from ..strategies.sklearn_decision_path_strategy import SklearnDecisionPathStrategy
from ..strategies.xgboost_decision_path_strategy import XGBoostDecisionPathStrategy

logger = logging.getLogger(__name__)


class XAIStrategyFactory:
    @staticmethod
    def is_supported(xai_type: XAITypeEnum, model_type_enum: ModelTypeEnum) -> bool:
        """
        Checks if a given XAI technique is generally supported for a model type enum.
        This method does NOT require an actual model instance.
        """
        logger.debug(
            f"XAIStrategyFactory.is_supported: Checking xai_type='{xai_type.value}', model_type_enum='{model_type_enum.value}'"
        )

        if xai_type in [
            XAITypeEnum.SHAP,
            XAITypeEnum.LIME,
            XAITypeEnum.FEATURE_IMPORTANCE,
            XAITypeEnum.COUNTERFACTUALS,
        ]:
            # These strategies are generally applicable or have internal fallbacks.
            # Specific model compatibility is handled within the strategy itself.
            return True

        elif xai_type == XAITypeEnum.DECISION_PATH:
            sklearn_tree_based_enums = [
                ModelTypeEnum.SKLEARN_RANDOMFOREST,
                ModelTypeEnum.SKLEARN_DECISIONTREECLASSIFIER,
                ModelTypeEnum.SKLEARN_GRADIENTBOOSTINGCLASSIFIER,
                ModelTypeEnum.SKLEARN_ADABOOSTCLASSIFIER,
            ]
            if model_type_enum in sklearn_tree_based_enums:
                return True
            elif model_type_enum == ModelTypeEnum.XGBOOST_CLASSIFIER:
                return True
            elif model_type_enum == ModelTypeEnum.LIGHTGBM_CLASSIFIER:
                return True
            else:
                logger.debug(
                    f"Decision Path not supported for model_type_enum: {model_type_enum.value} by default."
                )
                return False  # Decision path not supported for other enums by default
        else:
            logger.warning(
                f"XAIStrategyFactory.is_supported: Unknown XAI type '{xai_type.value}' encountered."
            )
            return False

    @staticmethod
    def create(
        xai_type: XAITypeEnum,
        model: Any,  # The actual trained model instance
        model_type_enum: ModelTypeEnum,  # The ModelTypeEnum of the model from DB
        background_data: Optional[pd.DataFrame] = None,
        feature_names: Optional[List[str]] = None,
    ) -> BaseXAIStrategy:

        if model is None:
            logger.error(
                f"XAIStrategyFactory.create: CRITICAL - Received a None model instance for XAI type '{xai_type.value}' and model type enum '{model_type_enum.value}'. Cannot create strategy."
            )
            raise ValueError(
                "Model instance cannot be None for XAIStrategyFactory.create."
            )

        logger.info(
            f"XAIStrategyFactory.create: Creating XAI strategy for XAI type '{xai_type.value}' using model_type_enum '{model_type_enum.value}'."
        )

        if xai_type == XAITypeEnum.SHAP:
            return SHAPStrategy(model, background_data)

        elif xai_type == XAITypeEnum.LIME:
            return LIMEStrategy(model, background_data)

        elif xai_type == XAITypeEnum.FEATURE_IMPORTANCE:
            return FeatureImportanceStrategy(model, background_data)

        elif xai_type == XAITypeEnum.DECISION_PATH:
            sklearn_tree_based_enums = [
                ModelTypeEnum.SKLEARN_RANDOMFOREST,
                ModelTypeEnum.SKLEARN_DECISIONTREECLASSIFIER,
                ModelTypeEnum.SKLEARN_GRADIENTBOOSTINGCLASSIFIER,
                ModelTypeEnum.SKLEARN_ADABOOSTCLASSIFIER,
            ]

            if model_type_enum in sklearn_tree_based_enums:
                logger.debug(
                    f"XAIStrategyFactory.create: Selected SklearnDecisionPathStrategy for enum {model_type_enum.value}."
                )
                return SklearnDecisionPathStrategy(model)
            elif model_type_enum == ModelTypeEnum.XGBOOST_CLASSIFIER:
                logger.debug(
                    f"XAIStrategyFactory.create: Selected XGBoostDecisionPathStrategy for enum {model_type_enum.value}."
                )
                return XGBoostDecisionPathStrategy(model)
            elif model_type_enum == ModelTypeEnum.LIGHTGBM_CLASSIFIER:
                logger.debug(
                    f"XAIStrategyFactory.create: Selected LightGBMDecisionPathStrategy for enum {model_type_enum.value}."
                )
                return LightGBMDecisionPathStrategy(model)
            else:
                logger.error(
                    f"XAIStrategyFactory.create: Decision Path strategy creation failed. Unsupported model_type_enum: {model_type_enum.value}."
                )
                raise ValueError(
                    f"Decision Path strategy creation failed. Unsupported model_type_enum: {model_type_enum.value}."
                )

        elif xai_type == XAITypeEnum.COUNTERFACTUALS:
            return CounterfactualsStrategy(model, background_data)

        else:
            logger.error(
                f"XAIStrategyFactory.create: Unsupported XAI type requested for creation: {xai_type.value}"
            )
            raise ValueError(
                f"Unsupported XAI type in factory.create: {xai_type.value}"
            )
