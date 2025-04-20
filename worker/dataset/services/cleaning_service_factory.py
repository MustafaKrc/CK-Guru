# worker/dataset/services/cleaning_service_factory.py

import logging
from typing import Dict, List, Any, Type # Import Type

# Import base class and specific implementations
from .cleaning_service_base import BaseCleaningService
from .cleaning_service import RuleBasedCleaningService
#from .alternative_cleaning_service import AlgorithmicCleaningService # Assuming this exists

# Import CleaningRuleBase for type hint
from .cleaning_rules.base import CleaningRuleBase

logger = logging.getLogger(__name__)

def get_cleaning_service(
    dataset_config: Dict[str, Any],
    rule_registry: Dict[str, Type[CleaningRuleBase]] # Accept the registry
) -> BaseCleaningService:
    """Factory function to instantiate the appropriate cleaning service."""
    strategy_name = dataset_config.get('cleaning_strategy', 'rule_based')
    rules_config = dataset_config.get('cleaning_rules', [])

    logger.info(f"Creating cleaning service for strategy: '{strategy_name}'")

    if strategy_name == "rule_based":
        # Pass the registry to the RuleBased service
        return RuleBasedCleaningService(rules_config, dataset_config, rule_registry)
    # elif strategy_name == "algorithmic_v1":
    #     # Algorithmic service might not need the rule registry, but accepts same signature
    #     return AlgorithmicCleaningService(rules_config, dataset_config)
    else:
        logger.error(f"Unknown cleaning strategy: '{strategy_name}'. Falling back to rule_based.")
        # Fallback still needs the registry
        return RuleBasedCleaningService(rules_config, dataset_config, rule_registry)