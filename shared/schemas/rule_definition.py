# shared/schemas/rule_definition.py
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class RuleParamDefinition(BaseModel):
    name: str = Field(..., description="Parameter name used in the config.")
    type: str = Field(
        ..., description="Data type (e.g., 'integer', 'float', 'boolean', 'string')."
    )
    description: str = Field(
        ..., description="User-friendly description of the parameter."
    )
    default: Optional[Any] = Field(
        None, description="Default value if not provided in config."
    )
    # Add a 'required' field if needed, although Pydantic handles required based on Optional/Ellipsis/Default
    required: bool = Field(
        default=False,
        description="Indicates if the parameter is mandatory (validation handled by presence/default).",
    )


class RuleDefinition(BaseModel):
    """
    Schema representing an available cleaning rule, returned by the API.
    Derived from the CleaningRuleDefinitionDB model.
    """

    name: str = Field(..., description="Unique identifier name of the cleaning rule.")
    description: str = Field(
        ..., description="User-friendly explanation of what the rule does."
    )
    parameters: List[RuleParamDefinition] = Field(
        default_factory=list, description="Parameters the rule accepts."
    )
    # Add fields present in the DB model that are useful for the API consumer
    is_batch_safe: bool = Field(
        ...,
        description="Indicates if the rule can operate safely on data batches independently.",
    )
    is_implemented: bool = Field(
        ...,
        description="Indicates if the rule implementation exists and is active in the worker.",
    )

    # Pydantic V2 configuration for ORM mode (reading attributes from DB models)
    model_config = ConfigDict(from_attributes=True)
