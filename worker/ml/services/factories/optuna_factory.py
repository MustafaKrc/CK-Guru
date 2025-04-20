# worker/ml/services/factories/optuna_factory.py
import logging
from typing import Dict, Any, Optional

import optuna

# Import Enum types from shared schemas
from shared.schemas.hp_search_job import SamplerTypeEnum, PrunerTypeEnum

logger = logging.getLogger(__name__)

def create_sampler(sampler_type_str: Optional[str], params: Dict[str, Any], seed: int) -> Optional[optuna.samplers.BaseSampler]:
    """Factory function to create Optuna samplers."""
    # Use default from Enum if string is None or empty
    sampler_type_enum = SamplerTypeEnum(sampler_type_str) if sampler_type_str else SamplerTypeEnum.TPE
    sampler_type = sampler_type_enum.value.lower()

    logger.info(f"Creating Optuna sampler of type: '{sampler_type}' with params: {params}")
    try:
        if sampler_type == SamplerTypeEnum.TPE.value:
            return optuna.samplers.TPESampler(seed=seed, **params)
        elif sampler_type == SamplerTypeEnum.RANDOM.value:
            return optuna.samplers.RandomSampler(seed=seed, **params)
        elif sampler_type == SamplerTypeEnum.CMAES.value:
            if not params:
                 logger.warning("CMA-ES sampler selected without specific parameters. Using Optuna defaults.")
            # CMAESampler might not accept all params directly, check Optuna docs
            return optuna.samplers.CmaEsSampler(seed=seed, **params)
        # Add other samplers here based on SamplerTypeEnum
        else:
            logger.warning(f"Unsupported sampler type '{sampler_type}'. Falling back to TPESampler.")
            return optuna.samplers.TPESampler(seed=seed)
    except Exception as e:
        logger.error(f"Failed to create sampler type '{sampler_type}' with params {params}: {e}", exc_info=True)
        logger.warning("Falling back to default TPESampler due to error.")
        return optuna.samplers.TPESampler(seed=seed) # Fallback on error

def create_pruner(pruner_type_str: Optional[str], params: Dict[str, Any], seed: Optional[int] = None) -> Optional[optuna.pruners.BasePruner]:
    """Factory function to create Optuna pruners."""
    # Use default from Enum if string is None or empty
    pruner_type_enum = PrunerTypeEnum(pruner_type_str) if pruner_type_str else PrunerTypeEnum.MEDIAN
    pruner_type = pruner_type_enum.value.lower()

    logger.info(f"Creating Optuna pruner of type: '{pruner_type}' with params: {params}")
    # Seed is not typically used for pruners, ignore it for now
    try:
        if pruner_type == PrunerTypeEnum.MEDIAN.value:
            return optuna.pruners.MedianPruner(**params)
        elif pruner_type == PrunerTypeEnum.HYPERBAND.value:
            return optuna.pruners.HyperbandPruner(**params)
        elif pruner_type == PrunerTypeEnum.NOP.value:
            return optuna.pruners.NopPruner()
        elif pruner_type == PrunerTypeEnum.PERCENTILE.value:
            return optuna.pruners.PercentilePruner(**params)
        elif pruner_type == PrunerTypeEnum.SUCCESSIVEHALVING.value:
             return optuna.pruners.SuccessiveHalvingPruner(**params)
        # Add other pruners here based on PrunerTypeEnum
        else:
            logger.warning(f"Unsupported pruner type '{pruner_type}'. Falling back to MedianPruner.")
            return optuna.pruners.MedianPruner()
    except Exception as e:
        logger.error(f"Failed to create pruner type '{pruner_type}' with params {params}: {e}", exc_info=True)
        logger.warning("Falling back to default MedianPruner due to error.")
        return optuna.pruners.MedianPruner() # Fallback on error