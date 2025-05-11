# worker/ml/services/factories/strategy_factory.py
import logging
from typing import Dict  # Add Any

from services.interfaces import IArtifactService
from shared.schemas.enums import ModelTypeEnum

# Import Strategies
from ..strategies.base_strategy import BaseModelStrategy
from ..strategies.sklearn_strategy import SklearnStrategy

# from ..strategies.pytorch_strategy import PyTorchStrategy # Example


logger = logging.getLogger(__name__)


def create_model_strategy(
    model_type: ModelTypeEnum,
    model_config: Dict,
    job_config: Dict,
    artifact_service: IArtifactService,
) -> BaseModelStrategy:
    """
    Factory function to instantiate the appropriate ML model execution strategy,
    injecting the ArtifactService.
    """
    if model_type == ModelTypeEnum.SKLEARN_RANDOMFOREST:
        logger.debug("Instantiating SklearnStrategy for RandomForest.")
        # Pass artifact_service to the constructor
        return SklearnStrategy(model_type, model_config, job_config, artifact_service)
    # Example for future PyTorch integration
    # elif model_type == ModelTypeEnum.PYTORCH_CNN:
    #     logger.debug("Instantiating PyTorchStrategy.")
    #     return PyTorchStrategy(model_type, model_config, job_config, artifact_service)
    else:
        logger.error(
            f"No strategy implementation found for model type: {model_type.value}"
        )
        raise ValueError(
            f"Unsupported model type for strategy factory: {model_type.value}"
        )
