# shared/schemas/ml_model_type_definition.py
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# This schema should align with frontend/types/jobs.ts -> HyperparameterDefinition
class HyperparameterDefinitionSchema(BaseModel):
    name: str
    type: str  # e.g., "integer", "float", "string", "boolean", "enum", "text_choice"
    description: Optional[str] = None
    default_value: Optional[Any] = None
    example_value: Optional[Any] = None
    options: Optional[List[Dict[str, Any]]] = (
        None  # e.g., [{"value": "gini", "label": "Gini Impurity"}]
    )
    range: Optional[Dict[str, Optional[float]]] = (
        None  # e.g., {"min": 0.1, "max": 1.0, "step": 0.01}
    )
    required: Optional[bool] = False


class MLModelTypeDefinitionBase(BaseModel):
    type_name: str = Field(
        ..., description="Internal name from ModelTypeEnum as string"
    )
    display_name: str = Field(..., description="User-friendly display name")
    description: Optional[str] = Field(
        None, description="Description of the model type"
    )
    hyperparameter_schema: List[HyperparameterDefinitionSchema] = Field(
        default_factory=list, description="Schema defining configurable hyperparameters"
    )
    is_enabled: bool = Field(
        True, description="If this model type is available for selection"
    )


class MLModelTypeDefinitionCreate(MLModelTypeDefinitionBase):
    last_updated_by: Optional[str] = None


class MLModelTypeDefinitionUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    hyperparameter_schema: Optional[List[HyperparameterDefinitionSchema]] = None
    is_enabled: Optional[bool] = None
    last_updated_by: Optional[str] = None


class MLModelTypeDefinitionRead(MLModelTypeDefinitionBase):

    model_config = {
        "from_attributes": True,
        "use_enum_values": True,
    }


# This is what the frontend expects from /ml/model-types
class AvailableModelTypeResponse(BaseModel):
    type_name: str = Field(
        ..., description="Model type name as string from ModelTypeEnum"
    )
    display_name: str
    description: Optional[str] = None
    hyperparameter_schema: List[HyperparameterDefinitionSchema]

    model_config = {"from_attributes": True, "use_enum_values": True}
