# shared/cleaning_rules_base.py
from abc import ABC, abstractmethod
import logging
from typing import List, Dict, Any, Optional, Type
from pydantic import BaseModel, Field
import pandas as pd

# --- Re-use schema definitions for consistency ---
class RuleParamDefinition(BaseModel):
    name: str
    type: str
    description: str
    default: Optional[Any] = None

class RuleDefinition(BaseModel):
    name: str
    description: str
    parameters: List[RuleParamDefinition] = Field(default_factory=list)
    is_batch_safe: bool = True # Default to True, implementations override if needed
    is_implemented: bool = True # Assume implemented if class exists

# --- Abstract Base Class for Rules ---
class CleaningRuleBase(ABC):
    # Class attributes to define metadata (alternative to decorator)
    rule_name: str = "base_rule_name" # Must be overridden by subclasses
    description: str = "Base rule description."
    parameters: List[RuleParamDefinition] = []
    is_batch_safe: bool = True # Override if rule requires global context

    def get_definition(self) -> RuleDefinition:
        """Returns the Pydantic model definition of the rule."""
        return RuleDefinition(
            name=self.rule_name,
            description=self.description,
            parameters=self.parameters,
            is_batch_safe=self.is_batch_safe,
            is_implemented=True # If the class exists, it's considered implemented
        )

    @abstractmethod
    def apply(self, df: pd.DataFrame, params: Dict[str, Any], config: Dict[str, Any]) -> pd.DataFrame:
        """
        Applies the cleaning rule to the DataFrame.

        Args:
            df: The input DataFrame batch.
            params: Dictionary of parameters specific to this rule execution,
                    taken from the dataset config.
            config: The full dataset configuration dictionary (e.g., for feature lists).

        Returns:
            The cleaned DataFrame.
        """
        pass

    def __init__(self):
        # Can add initialization logic if needed
        pass

# --- Registry (Worker Side) ---
# This dictionary will be populated by discovered rule classes in the worker
WORKER_RULE_REGISTRY: Dict[str, Type[CleaningRuleBase]] = {}

def register_rule(cls: Type[CleaningRuleBase]):
    """Class decorator or manual function to register rule implementations."""
    if not issubclass(cls, CleaningRuleBase) or cls is CleaningRuleBase:
        raise TypeError("Registered class must be a subclass of CleaningRuleBase")
    if not cls.rule_name or cls.rule_name == "base_rule_name":
         raise ValueError(f"Rule class {cls.__name__} must define a unique 'rule_name' attribute.")

    if cls.rule_name in WORKER_RULE_REGISTRY:
        raise ValueError(f"Rule name '{cls.rule_name}' already registered.")

    WORKER_RULE_REGISTRY[cls.rule_name] = cls
    logging.debug(f"Registered cleaning rule: {cls.rule_name}")
    return cls # Return class for use as decorator

def discover_rules(module_path: str = "worker.dataset.service.cleaning_rules"):
    """
    Imports the rules module to trigger registration via decorators/calls.
    (Could be more sophisticated later with pkgutil if rules are split).
    """
    try:
        import importlib
        importlib.import_module(module_path)
        logging.info(f"Discovered and registered {len(WORKER_RULE_REGISTRY)} cleaning rules.")
    except ImportError as e:
        logging.error(f"Could not discover rules from module '{module_path}': {e}")

def get_rule_instance(name: str) -> Optional[CleaningRuleBase]:
    """Gets an instance of a registered rule class."""
    rule_cls = WORKER_RULE_REGISTRY.get(name)
    if rule_cls:
        return rule_cls() # Instantiate the rule
    return None