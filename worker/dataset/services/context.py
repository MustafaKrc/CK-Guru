# worker/dataset/services/context.py
from typing import Optional, List, Dict, Any
from pathlib import Path

from pydantic import BaseModel, Field, ConfigDict
from celery import Task
import pandas as pd

# Import models needed for context typing
from shared.db.models import Dataset, Repository, BotPattern
from shared.schemas.dataset import DatasetConfig # Use the schema for config

class DatasetContext(BaseModel):
    """Holds state shared between dataset generation steps."""
    model_config = ConfigDict(arbitrary_types_allowed=True) # Allow complex types like Task, Path, DataFrame

    # --- Input & Configuration ---
    dataset_id: int = Field(..., description="ID of the dataset being generated.")
    dataset_db: Optional[Dataset] = Field(None, description="The loaded Dataset ORM object.")
    repository_db: Optional[Repository] = Field(None, description="The loaded Repository ORM object.")
    bot_patterns_db: List[BotPattern] = Field(default_factory=list, description="Loaded BotPattern ORM objects.")
    dataset_config: Optional[DatasetConfig] = Field(None, description="Parsed dataset configuration.")

    # --- Task Management ---
    task_instance: Optional[Task] = Field(None, description="Celery Task instance for status updates.")
    warnings: List[str] = Field(default_factory=list, description="List of non-critical warnings during processing.")

    # --- Processing State & Data ---
    estimated_total_rows: int = Field(1, description="Estimated rows from initial query.") # Default 1 to avoid div zero
    # Store processed batch data (e.g., list of DataFrames or combined DataFrame)
    processed_batches_data: Optional[List[pd.DataFrame]] = Field(None, description="Data from processed batches, before global processing.")
    processed_dataframe: Optional[pd.DataFrame] = Field(None, description="DataFrame after processing steps.")

    # --- Output ---
    final_dataframe: Optional[pd.DataFrame] = Field(None, description="Final DataFrame after column selection.")
    output_storage_uri: Optional[str] = Field(None, description="S3 URI for the main output Parquet file.")
    background_sample_uri: Optional[str] = Field(None, description="S3 URI for the background sample Parquet file.")
    rows_written: int = Field(0, description="Number of rows written to the final dataset file.")