# worker/dataset/services/cleaning_rules/base.py
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Type

import pandas as pd

from shared.schemas.rule_definition import RuleDefinition, RuleParamDefinition


# --- Abstract Base Class (Remains the same) ---
class CleaningRuleBase(ABC):
    rule_name: str = "base_rule_name"
    description: str = "Base rule description."
    parameters: List[RuleParamDefinition] = []
    is_batch_safe: bool = True

    def get_definition(self) -> RuleDefinition:
        return RuleDefinition(
            name=self.rule_name,
            description=self.description,
            parameters=self.parameters,
            is_batch_safe=self.is_batch_safe,
            is_implemented=True,
        )

    @abstractmethod
    def apply(
        self, df: pd.DataFrame, params: Dict[str, Any], config: Dict[str, Any]
    ) -> pd.DataFrame:
        pass

    def __init__(self):
        pass


# --- Registry & Discovery (Modified to emphasize non-global use after discovery) ---
WORKER_RULE_REGISTRY: Dict[str, Type[CleaningRuleBase]] = {}
logger = logging.getLogger(__name__)


def register_rule(cls: Type[CleaningRuleBase]):
    """Class decorator to register rule implementations in the global registry."""
    # (Validation logic remains the same)
    if not issubclass(cls, CleaningRuleBase) or cls is CleaningRuleBase:
        raise TypeError("Registered class must be a subclass of CleaningRuleBase")
    if not cls.rule_name or cls.rule_name == "base_rule_name":
        raise ValueError(
            f"Rule class {cls.__name__} must define a unique 'rule_name' attribute."
        )

    if cls.rule_name in WORKER_RULE_REGISTRY:
        logger.warning(
            f"Rule name '{cls.rule_name}' from class {cls.__name__} already registered. Overwriting."
        )

    WORKER_RULE_REGISTRY[cls.rule_name] = cls
    logger.debug(f"Registered cleaning rule: {cls.rule_name}")
    return cls


def discover_rules(module_path: str = "services.cleaning_rules.implementations"):
    """
    Imports the rules module(s) to populate the global WORKER_RULE_REGISTRY.
    This should be called once at worker startup.
    """
    try:
        import importlib

        importlib.invalidate_caches()
        importlib.import_module(module_path)
        logger.info(
            f"Rule discovery complete. {len(WORKER_RULE_REGISTRY)} rules registered globally from '{module_path}'."
        )
    except ImportError as e:
        logger.error(f"Could not discover rules from module '{module_path}': {e}")
    except Exception as e:
        logger.error(
            f"Error during rule discovery from '{module_path}': {e}", exc_info=True
        )
