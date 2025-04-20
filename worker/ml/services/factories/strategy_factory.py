# worker/ml/services/factories/strategy_factory.py
import logging
from typing import Dict

# Import Strategies
from ..strategies.base_strategy import BaseModelStrategy
from ..strategies.sklearn_strategy import SklearnStrategy
# from ..strategies.pytorch_strategy import PyTorchStrategy # Example for future

from shared.schemas.enums import ModelTypeEnum

logger = logging.getLogger(__name__)

def create_model_strategy(model_type: ModelTypeEnum, model_config: Dict, job_config: Dict) -> BaseModelStrategy:
    """
    Factory function to instantiate the appropriate ML model execution strategy.

    Args:
        model_type: String identifying the type of model (e.g., 'sklearn_randomforest').
        model_config: Configuration/hyperparameters specific to the model instance.
        job_config: Overall job configuration (seed, evaluation settings, etc.).

    Returns:
        An instance of a BaseModelStrategy subclass.

    Raises:
        ValueError: If the model_type is unsupported.
    """
    if model_type == ModelTypeEnum.SKLEARN_RANDOMFOREST:
        logger.debug("Instantiating SklearnStrategy for RandomForest.")
        # Pass the enum member or its value, SklearnStrategy can handle either
        # Let's pass the enum member for consistency
        return SklearnStrategy(model_type, model_config, job_config)
    # Example for future PyTorch integration
    # elif model_type == ModelTypeEnum.PYTORCH_CNN:
    #     logger.debug("Instantiating PyTorchStrategy.")
    #     return PyTorchStrategy(model_type, model_config, job_config)
    else:
        # Log the string value of the unsupported type
        logger.error(f"No strategy implementation found for model type: {model_type.value}")
        raise ValueError(f"Unsupported model type for strategy factory: {model_type.value}")