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
