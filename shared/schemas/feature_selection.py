# shared/schemas/feature_selection.py
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class FeatureSelectionParamDefinition(BaseModel):
    """Schema for a feature selection algorithm's parameter definition."""
    name: str = Field(..., description="Parameter name used in the config.")
    type: str = Field(..., description="Data type (e.g., 'integer', 'float', 'string', 'enum').")
    description: str = Field(..., description="User-friendly description of the parameter.")
    default: Optional[Any] = Field(None, description="Default value if not provided.")
    options: Optional[List[Any]] = Field(None, description="List of valid choices for 'enum' type.")
    range: Optional[Dict[str, Optional[float]]] = Field(None, description="e.g., {'min': 0.1, 'max': 1.0, 'step': 0.01}")


class FeatureSelectionDefinitionRead(BaseModel):
    """Schema for returning available feature selection algorithms to the API consumer."""
    name: str
    display_name: str
    description: str
    parameters: List[FeatureSelectionParamDefinition]
    is_implemented: bool

    model_config = ConfigDict(from_attributes=True)