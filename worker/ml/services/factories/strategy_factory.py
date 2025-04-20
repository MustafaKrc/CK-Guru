# worker/ml/services/factories/strategy_factory.py
import logging
from typing import Dict

# Import Strategies
from ..strategies.base_strategy import BaseModelStrategy
from ..strategies.sklearn_strategy import SklearnStrategy
# from ..strategies.pytorch_strategy import PyTorchStrategy # Example for future

logger = logging.getLogger(__name__)

def create_model_strategy(model_type: str, model_config: Dict, job_config: Dict) -> BaseModelStrategy:
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
    logger.info(f"Attempting to create model strategy for type: {model_type}")

    if model_type.startswith('sklearn_'):
        logger.debug("Instantiating SklearnStrategy.")
        return SklearnStrategy(model_config, job_config)
    # Example for future PyTorch integration
    # elif model_type.startswith('pytorch_'):
    #     logger.debug("Instantiating PyTorchStrategy.")
    #     return PyTorchStrategy(model_config, job_config)
    else:
        logger.error(f"No strategy implementation found for model type: {model_type}")
        raise ValueError(f"Unsupported model type for strategy factory: {model_type}")