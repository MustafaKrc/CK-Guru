# worker/dataset/services/cleaning_service_factory.py
import logging
from typing import Dict, List, Any, Type

# Import base interface and specific implementations
from services.interfaces import ICleaningService
from services.cleaning_service import RuleBasedCleaningService

from services.cleaning_rules.base import CleaningRuleBase

logger = logging.getLogger(__name__)

def get_cleaning_service(
    dataset_config: Dict[str, Any],
    rule_registry: Dict[str, Type[CleaningRuleBase]]
) -> ICleaningService: 
    """Factory function to instantiate the appropriate cleaning service."""
    strategy_name = dataset_config.get('cleaning_strategy', 'rule_based')
    rules_config = dataset_config.get('cleaning_rules', [])

    logger.info(f"Creating cleaning service for strategy: '{strategy_name}'")

    if strategy_name == "rule_based":
        return RuleBasedCleaningService(rules_config, dataset_config, rule_registry)
    # elif strategy_name == "algorithmic_v1":
    #     return AlgorithmicCleaningService(rules_config, dataset_config)
    else:
        logger.error(f"Unknown cleaning strategy: '{strategy_name}'. Falling back to rule_based.")
        return RuleBasedCleaningService(rules_config, dataset_config, rule_registry)