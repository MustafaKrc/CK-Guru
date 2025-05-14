# worker/ml/services/factories/model_strategy_factory.py
import logging
from typing import Any, Dict  # Add Any

# Import IArtifactService interface
from services.interfaces.i_artifact_service import IArtifactService

# Import ModelTypeEnum from shared schemas
from shared.schemas.enums import ModelTypeEnum

# Import the base strategy and concrete strategies
from ..strategies.base_strategy import BaseModelStrategy
from ..strategies.lightgbm_strategy import LightGBMStrategy
from ..strategies.sklearn_strategy import SklearnStrategy
from ..strategies.xgboost_strategy import XGBoostStrategy

logger = logging.getLogger(__name__)


def create_model_strategy(
    model_type: ModelTypeEnum,
    model_config: Dict[str, Any],  # Hyperparameters for the specific model instance
    job_config: Dict[str, Any],  # Overall job config (e.g., random_seed, split_size)
    artifact_service: IArtifactService,  # Injected artifact service
) -> BaseModelStrategy:
    """
    Factory function to instantiate the appropriate ML model execution strategy,
    injecting necessary configurations and the ArtifactService.
    """
    logger.info(
        f"ModelStrategyFactory: Creating strategy for model type: {model_type.value}"
    )

    # Scikit-learn models can share the SklearnStrategy
    if model_type.value.startswith("sklearn_"):
        logger.debug(f"Instantiating SklearnStrategy for {model_type.value}.")
        return SklearnStrategy(
            model_type=model_type,  # Pass the enum member
            model_config=model_config,
            job_config=job_config,
            artifact_service=artifact_service,
        )
    elif model_type == ModelTypeEnum.XGBOOST_CLASSIFIER:
        logger.debug("Instantiating XGBoostStrategy.")
        return XGBoostStrategy(
            model_type=model_type,
            model_config=model_config,
            job_config=job_config,
            artifact_service=artifact_service,
        )
    elif model_type == ModelTypeEnum.LIGHTGBM_CLASSIFIER:
        logger.debug("Instantiating LightGBMStrategy.")
        return LightGBMStrategy(
            model_type=model_type,
            model_config=model_config,
            job_config=job_config,
            artifact_service=artifact_service,
        )
    else:
        logger.error(
            f"ModelStrategyFactory: No strategy implementation found for model type: {model_type.value}"
        )
        raise ValueError(
            f"Unsupported model type for strategy factory: {model_type.value}"
        )
