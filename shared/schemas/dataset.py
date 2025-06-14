# shared/schemas/dataset.py
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field  # Use Json for validation? maybe just Dict

from shared.schemas.enums import DatasetStatusEnum, FeatureSelectionAlgorithmEnum
from shared.schemas.repository import RepositoryRead


# --- Feature Selection Configuration ---
class FeatureSelectionConfig(BaseModel):
    name: FeatureSelectionAlgorithmEnum = Field(
        ..., description="Name of the feature selection algorithm to apply."
    )
    params: Dict[str, Any] = Field(
        default_factory=dict, description="Parameters for the selected algorithm."
    )


# --- Cleaning Rule Configuration ---
class CleaningRuleParams(BaseModel):
    # Define potential parameters rules might use
    # Use Optional for flexibility if not all rules need all params
    gap_seconds: Optional[int] = None
    min_line_change: Optional[int] = None
    threshold: Optional[int] = None  # Generic threshold for rules 12, 13, 14, cluster
    max_files_changed: Optional[int] = None  # Specific for rule 14 if needed


class CleaningRuleConfig(BaseModel):
    name: str = Field(..., description="Unique identifier name of the cleaning rule.")
    enabled: bool = Field(
        default=True, description="Whether this rule should be applied."
    )
    params: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Parameters specific to this rule."
    )  # Use Dict[str, Any]


# --- Dataset Configuration ---
class DatasetConfig(BaseModel):
    feature_columns: List[str] = Field(
        ..., description="List of column names to include as features."
    )
    target_column: str = Field(
        ..., description="Name of the target variable column (e.g., 'is_buggy')."
    )
    cleaning_rules: List[CleaningRuleConfig] = Field(
        default_factory=list, description="Configuration for cleaning rules to apply."
    )
    feature_selection: Optional[FeatureSelectionConfig] = Field(
        None,
        description="Configuration for the feature selection step, which runs after cleaning.",
    )


# --- Dataset Schemas ---
class DatasetBase(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    config: DatasetConfig  # Embed the config schema


class DatasetCreate(DatasetBase):
    pass  # Input fields are defined in Base and Config


class DatasetRead(DatasetBase):
    id: int
    repository_id: int
    repository: Optional[RepositoryRead] = None
    status: DatasetStatusEnum  # This now correctly refers to the imported enum
    status_message: Optional[str] = None
    storage_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    background_data_path: Optional[str] = None
    num_rows: Optional[int] = None

    model_config = {
        "from_attributes": True,  # Pydantic V2 way
        "use_enum_values": True,  # Serialize enums as strings
    }


class DatasetUpdate(DatasetBase):
    name: Optional[str] = None
    description: Optional[str] = None
    config: Optional[DatasetConfig] = None
    storage_path: Optional[str] = None
    background_data_path: Optional[str] = None


class DatasetStatusUpdate(BaseModel):
    status: DatasetStatusEnum  # This now correctly refers to the imported enum
    status_message: Optional[str] = None
    storage_path: Optional[str] = None
    background_data_path: Optional[str] = None


# --- Schema for Task Submission Response ---
class DatasetTaskResponse(BaseModel):
    dataset_id: int
    task_id: str


class PaginatedDatasetRead(BaseModel):
    items: List[DatasetRead]
    total: int
    skip: Optional[int] = None
    limit: Optional[int] = None
