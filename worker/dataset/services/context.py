# worker/dataset/services/context.py
from typing import Any, List, Optional

import pandas as pd
from celery import Task
from pydantic import BaseModel, ConfigDict, Field

# Import models needed for context typing
from shared.db.models import BotPattern, Dataset, Repository
from shared.schemas.dataset import DatasetConfig  # Use the schema for config
from shared.celery_config.base_task import EventPublishingTask 


class DatasetContext(BaseModel):
    """Holds state shared between dataset generation steps."""

    model_config = ConfigDict(
        arbitrary_types_allowed=True
    )  # Allow complex types like Task, Path, DataFrame

    # --- Input & Configuration ---
    dataset_id: int = Field(..., description="ID of the dataset being generated.")
    dataset_db: Optional[Dataset] = Field(
        None, description="The loaded Dataset ORM object."
    )
    repository_db: Optional[Repository] = Field(
        None, description="The loaded Repository ORM object."
    )
    bot_patterns_db: List[BotPattern] = Field(
        default_factory=list, description="Loaded BotPattern ORM objects."
    )
    dataset_config: Optional[DatasetConfig] = Field(
        None, description="Parsed dataset configuration."
    )

    # --- Task Management ---
    task_instance: Optional[EventPublishingTask] = Field(
        None, description="Celery Task instance for status updates."
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="List of non-critical warnings during processing.",
    )

    # --- Processing State & Data ---
    estimated_total_rows: int = Field(
        1, description="Estimated rows from initial query."
    )  # Default 1 to avoid div zero
    # Store processed batch data (e.g., list of DataFrames or combined DataFrame)
    processed_batches_data: Optional[List[pd.DataFrame]] = Field(
        None, description="Data from processed batches, before global processing."
    )
    processed_dataframe: Optional[pd.DataFrame] = Field(
        None, description="DataFrame after processing steps."
    )

    # --- Output ---
    final_dataframe: Optional[pd.DataFrame] = Field(
        None, description="Final DataFrame after column selection."
    )
    output_storage_uri: Optional[str] = Field(
        None, description="S3 URI for the main output Parquet file."
    )
    background_sample_uri: Optional[str] = Field(
        None, description="S3 URI for the background sample Parquet file."
    )
    rows_written: int = Field(
        0, description="Number of rows written to the final dataset file."
    )

    event_job_type: Optional[str] = None
    event_entity_id: Optional[Any] = None
    event_entity_type: Optional[str] = None
    event_user_id: Optional[Any] = None

    # Pydantic V2 uses model_validator or default_factory for this
    # If you are passing all args to __init__, this is fine:
    def __init__(self, **data: Any):
        super().__init__(**data)
        # Ensure lists are initialized if they are part of **data but could be None
        self.warnings = data.get('warnings', [])
        self.processed_batches_data = data.get('processed_batches_data', []) 
        # Ensure event context fields are set if passed, or remain None
        self.event_job_type = data.get('event_job_type')
        self.event_entity_id = data.get('event_entity_id')
        self.event_entity_type = data.get('event_entity_type')
        self.event_user_id = data.get('event_user_id')
