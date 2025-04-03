# backend/app/schemas/rule_definition.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class RuleParamDefinition(BaseModel):
    name: str = Field(..., description="Parameter name used in the config.")
    type: str = Field(..., description="Data type (e.g., 'integer', 'float', 'boolean', 'string').")
    description: str = Field(..., description="User-friendly description of the parameter.")
    default: Optional[Any] = Field(None, description="Default value if not provided in config.")

class RuleDefinition(BaseModel):
    name: str = Field(..., description="Unique identifier name of the cleaning rule.")
    description: str = Field(..., description="User-friendly explanation of what the rule does.")
    parameters: List[RuleParamDefinition] = Field(default_factory=list, description="Parameters the rule accepts.")